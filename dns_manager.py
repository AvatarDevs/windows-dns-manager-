import ctypes
import os
import sys
import json
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QComboBox, QSystemTrayIcon, QMenu, QAction, QProgressDialog
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QPropertyAnimation, QTimer

ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"dns.manager.app")

PROFILE_FILE = 'dns_profiles.json'
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW

# =======================
# Windows DNS Functions
# =======================

def get_interfaces():
    try:
        output = subprocess.check_output(
            ['netsh', 'interface', 'show', 'interface'], encoding='utf-8', creationflags=CREATE_NO_WINDOW)
        lines = output.splitlines()[3:]
        interfaces = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 4:
                interface_name = ' '.join(parts[3:])
                interfaces.append(interface_name)
        return interfaces
    except Exception as e:
        return []

def get_current_dns(interface):
    try:
        output = subprocess.check_output(
            ['netsh', 'interface', 'ip', 'show', 'dns', f'name="{interface}"'], encoding='utf-8', creationflags=CREATE_NO_WINDOW)
        return output
    except Exception as e:
        return str(e)

def set_dns(profile, interface):
    try:
        subprocess.check_call([
            'netsh', 'interface', 'ip', 'set', 'dns', f'name="{interface}"', 'static', profile['preferred']
        ], creationflags=CREATE_NO_WINDOW)
        if profile['alternate']:
            subprocess.check_call([
                'netsh', 'interface', 'ip', 'add', 'dns', f'name="{interface}"', profile['alternate'], 'index=2'
            ], creationflags=CREATE_NO_WINDOW)
        return True
    except Exception as e:
        return str(e)

def clear_dns(interface):
    try:
        subprocess.check_call([
            'netsh', 'interface', 'ip', 'set', 'dns', f'name="{interface}"', 'source=dhcp'
        ], creationflags=CREATE_NO_WINDOW)
        return True
    except Exception as e:
        return str(e)

def load_profiles():
    try:
        with open(PROFILE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_profiles(profiles):
    with open(PROFILE_FILE, 'w') as f:
        json.dump(profiles, f, indent=2)

# =======================
# Profile Dialog
# =======================

class ProfileDialog(QDialog):
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('DNS Profile')
        self.setFixedWidth(300)
        layout = QFormLayout(self)
        self.name = QLineEdit(self)
        self.preferred = QLineEdit(self)
        self.alternate = QLineEdit(self)
        if profile:
            self.name.setText(profile['name'])
            self.preferred.setText(profile['preferred'])
            self.alternate.setText(profile['alternate'])
        layout.addRow('Name:', self.name)
        layout.addRow('Preferred DNS:', self.preferred)
        layout.addRow('Alternate DNS:', self.alternate)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            'name': self.name.text(),
            'preferred': self.preferred.text(),
            'alternate': self.alternate.text()
        }

# =======================
# Main Application
# =======================

class DNSManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DNS Manager')
        self.setMinimumWidth(550)
        self.setWindowIcon(QIcon("icon.ico"))

        self.current_theme = 'dark'
        self.setStyleSheet(self.dark_theme())

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel('DNS Manager for Windows')
        title.setFont(QFont('Segoe UI', 16, QFont.Bold))
        header.addWidget(title)
        header.addStretch()

        self.theme_toggle = QPushButton("☀ Light Mode")
        self.theme_toggle.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_toggle)
        layout.addLayout(header)

        self.interfaces = get_interfaces()
        self.interface_box = QComboBox()
        self.interface_box.setFont(QFont("Segoe UI", 11))
        self.interface_box.setMinimumHeight(32)
        self.interface_box.setStyleSheet("QComboBox { padding: 6px; }")

        self.interface_box.addItems(self.interfaces)
        self.interface_box.currentIndexChanged.connect(self.refresh_dns)
        layout.addWidget(QLabel("Select Network Interface:"))
        layout.addWidget(self.interface_box)

        self.current_dns = QLabel()
        self.current_dns.setFont(QFont('Consolas', 10))
        self.current_dns.setWordWrap(True)
        layout.addWidget(QLabel('Current DNS:'))
        layout.addWidget(self.current_dns)

        btns = QHBoxLayout()
        self.btn_clear = QPushButton('Obtain DNS Automatically')
        self.btn_clear.clicked.connect(self.clear_dns)
        btns.addWidget(self.btn_clear)

        self.btn_refresh = QPushButton('Refresh')
        self.btn_refresh.clicked.connect(self.refresh_dns)
        btns.addWidget(self.btn_refresh)
        layout.addLayout(btns)

        layout.addWidget(QLabel('DNS Profiles:'))
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.load_profiles()

        btns2 = QHBoxLayout()
        self.btn_add = QPushButton('Add Profile')
        self.btn_add.clicked.connect(self.add_profile)
        btns2.addWidget(self.btn_add)
        self.btn_edit = QPushButton('Edit Profile')
        self.btn_edit.clicked.connect(self.edit_profile)
        btns2.addWidget(self.btn_edit)
        self.btn_remove = QPushButton('Remove Profile')
        self.btn_remove.clicked.connect(self.remove_profile)
        btns2.addWidget(self.btn_remove)
        self.btn_set = QPushButton('Set as Active')
        self.btn_set.clicked.connect(self.set_active)
        btns2.addWidget(self.btn_set)
        layout.addLayout(btns2)

        self.tray_icon = QSystemTrayIcon(QIcon("icon.ico"), self)
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("DNS Manager")
        self.tray_icon.show()

        self.refresh_dns()
    def light_theme(self):
        return """
            QWidget { background: #f5f6fa; color: #2f3640; }
            QPushButton {
                background: #0097e6;
                color: #fff;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 14px;
            }
            QPushButton:hover { background: #00a8ff; }
            QListWidget, QLineEdit {
                background: #dcdde1;
                border: 1px solid #ccc;
                color: #2f3640;
                padding: 4px;
            }
            QComboBox { padding: 4px; background: #dcdde1; color: #2f3640; }
            QLabel { font-size: 13px; }
        """

    def dark_theme(self):
        return """
            QWidget { background: #2f3640; color: #f5f6fa; }
            QPushButton {
                background: #00a8ff;
                color: #fff;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 14px;
            }
            QPushButton:hover { background: #0097e6; }
            QListWidget, QLineEdit {
                background: #353b48;
                border: 1px solid #444;
                color: #f5f6fa;
                padding: 4px;
            }
            QComboBox { padding: 4px; background: #353b48; color: #f5f6fa; }
            QLabel { font-size: 13px; }
        """

    def toggle_theme(self):
        if self.current_theme == 'dark':
            self.setStyleSheet(self.light_theme())
            self.theme_toggle.setText("🌙 Dark Mode")
            self.current_theme = 'light'
        else:
            self.setStyleSheet(self.dark_theme())
            self.theme_toggle.setText("☀ Light Mode")
            self.current_theme = 'dark'


    def selected_interface(self):
        return self.interface_box.currentText()

    def refresh_dns(self):
        interface = self.selected_interface()
        self.current_dns.setText(get_current_dns(interface))
        self.fade_widget(self.current_dns)

    def fade_widget(self, widget):
        self.anim = QPropertyAnimation(widget, b"windowOpacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def show_loading(self, message="Please wait..."):
        dialog = QProgressDialog(message, None, 0, 0, self)
        dialog.setWindowTitle("Working...")
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.show()
        return dialog

    def clear_dns(self):
        loading = self.show_loading("Clearing DNS...")
        QTimer.singleShot(100, lambda: self._clear_dns(loading))

    def _clear_dns(self, loading):
        result = clear_dns(self.selected_interface())
        loading.close()
        QMessageBox.information(self, 'Success', 'DNS set to automatic.' if result is True else str(result))
        self.refresh_dns()

    def load_profiles(self):
        self.profiles = load_profiles()
        self.list.clear()
        for p in self.profiles:
            item = QListWidgetItem(f"{p['name']} ({p['preferred']}, {p['alternate']})")
            self.list.addItem(item)

    def add_profile(self):
        dlg = ProfileDialog(parent=self)
        if dlg.exec_():
            data = dlg.get_data()
            if not data['name'] or not data['preferred']:
                QMessageBox.warning(self, 'Error', 'Name and Preferred DNS are required.')
                return
            self.profiles.append(data)
            save_profiles(self.profiles)
            self.load_profiles()

    def edit_profile(self):
        row = self.list.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Error', 'Select a profile to edit.')
            return
        dlg = ProfileDialog(self.profiles[row], parent=self)
        if dlg.exec_():
            self.profiles[row] = dlg.get_data()
            save_profiles(self.profiles)
            self.load_profiles()

    def remove_profile(self):
        row = self.list.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Error', 'Select a profile to remove.')
            return
        del self.profiles[row]
        save_profiles(self.profiles)
        self.load_profiles()

    def set_active(self):
        row = self.list.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Error', 'Select a profile to set.')
            return
        loading = self.show_loading("Setting DNS profile...")
        QTimer.singleShot(100, lambda: self._set_dns_profile(row, loading))

    def _set_dns_profile(self, row, loading):
        result = set_dns(self.profiles[row], self.selected_interface())
        loading.close()
        QMessageBox.information(self, 'Success', 'DNS set successfully.' if result is True else str(result))
        self.refresh_dns()

    def closeEvent(self, event):
        pass
        # event.ignore()
        # self.hide()
        # if self.tray_icon.isVisible():
        #     self.tray_icon.showMessage(
        #         "Running in Tray", "DNS Manager is still running in the background.",
        #         QSystemTrayIcon.Information, 3000)

# =======================
# Admin Elevation + Run
# =======================

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    win = DNSManager()
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit(0)
    main()
