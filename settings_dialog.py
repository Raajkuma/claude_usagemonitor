from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton
from config import save_config

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle("JARVIS HUD Settings")
        self.setFixedSize(300, 220)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Theme Selector
        layout.addWidget(QLabel("Interface Theme Style:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["jarvis_cyan", "jarvis_gold"])
        self.theme_combo.setCurrentText(self.config["theme"])
        layout.addWidget(self.theme_combo)

        # Click-Through Checkbox
        self.click_through_chk = QCheckBox("Enable Click-Through Mode")
        self.click_through_chk.setChecked(self.config["click_through"])
        layout.addWidget(self.click_through_chk)

        # Startup Checkbox
        self.startup_chk = QCheckBox("Start with Windows")
        self.startup_chk.setChecked(self.config["startup"])
        layout.addWidget(self.startup_chk)

        # Save Button
        save_btn = QPushButton("Apply & Save")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

    def save_settings(self):
        self.config["theme"] = self.theme_combo.currentText()
        self.config["click_through"] = self.click_through_chk.isChecked()
        self.config["startup"] = self.startup_chk.isChecked()
        save_config(self.config)
        self.accept()