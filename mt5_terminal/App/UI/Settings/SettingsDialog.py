"""
SettingsDialog.py — Configuration settings panel.
Allows editing watchlists, scan intervals, risk %, theme, and alert rules.
"""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QMessageBox, QWidget
)
from PySide6.QtCore import Qt

CONFIG_PATH = Path(__file__).resolve().parents[3] / 'Configs' / 'settings.json'


class SettingsDialog(QDialog):
    """User preferences & terminal configuration dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('MT5 Terminal Settings')
        self.setFixedWidth(500)
        self._load_config()
        self._build_ui()

    def _load_config(self) -> None:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self._cfg = json.load(f)
        else:
            self._cfg = {}

    def _save_config(self) -> None:
        symbols_str = self._symbols_edit.text()
        symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]

        self._cfg['symbols'] = symbols
        self._cfg['scan_interval_seconds'] = self._interval_spin.value()
        self._cfg['risk_percent'] = self._risk_spin.value()
        self._cfg['theme'] = self._theme_combo.currentText().lower()
        self._cfg['alert_sound'] = self._sound_chk.isChecked()
        self._cfg['alert_desktop'] = self._desktop_chk.isChecked()

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self._cfg, f, indent=2)

        QMessageBox.information(self, 'Settings Saved', 'Settings saved successfully. Restart may be required for theme changes.')
        self.accept()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Watchlist
        w_box = QGroupBox('WATCHLIST SYMBOLS (COMMA SEPARATED)')
        w_layout = QVBoxLayout(w_box)
        curr_syms = ', '.join(self._cfg.get('symbols', []))
        self._symbols_edit = QLineEdit(curr_syms)
        w_layout.addWidget(self._symbols_edit)
        layout.addWidget(w_box)

        # Scanning & Risk
        r_box = QGroupBox('SCANNING & RISK MANAGEMENT')
        r_layout = QVBoxLayout(r_box)

        int_row = QHBoxLayout()
        int_row.addWidget(QLabel('Scan Interval (seconds):'))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 300)
        self._interval_spin.setValue(self._cfg.get('scan_interval_seconds', 30))
        int_row.addWidget(self._interval_spin)
        r_layout.addLayout(int_row)

        risk_row = QHBoxLayout()
        risk_row.addWidget(QLabel('Account Risk per Trade (%):'))
        self._risk_spin = QDoubleSpinBox()
        self._risk_spin.setRange(0.1, 20.0)
        self._risk_spin.setSingleStep(0.5)
        self._risk_spin.setValue(self._cfg.get('risk_percent', 5.0))
        risk_row.addWidget(self._risk_spin)
        r_layout.addLayout(risk_row)

        layout.addWidget(r_box)

        # Appearance & Alerts
        a_box = QGroupBox('APPEARANCE & ALERTS')
        a_layout = QVBoxLayout(a_box)

        th_row = QHBoxLayout()
        th_row.addWidget(QLabel('Theme:'))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(['Dark', 'Light', 'Bloomberg'])
        curr_theme = self._cfg.get('theme', 'dark').capitalize()
        self._theme_combo.setCurrentText(curr_theme)
        th_row.addWidget(self._theme_combo)
        a_layout.addLayout(th_row)

        self._sound_chk = QCheckBox('Enable Audio Alert Sounds')
        self._sound_chk.setChecked(self._cfg.get('alert_sound', True))
        a_layout.addWidget(self._sound_chk)

        self._desktop_chk = QCheckBox('Enable Windows Desktop Notifications')
        self._desktop_chk.setChecked(self._cfg.get('alert_desktop', True))
        a_layout.addWidget(self._desktop_chk)

        layout.addWidget(a_box)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton('Save Settings')
        save_btn.setProperty('role', 'primary')
        save_btn.clicked.connect(self._save_config)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)
