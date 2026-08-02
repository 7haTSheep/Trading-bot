"""
StatusBarWidget.py — Bottom status bar for the main window.
"""
from __future__ import annotations
from PySide6.QtWidgets import QStatusBar, QLabel, QFrame
from PySide6.QtCore import Qt


class StatusBarWidget(QStatusBar):
    """Custom status bar for the main application window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self._build()

    def _build(self) -> None:
        self._scanner_lbl = QLabel('● Scanner Idle')
        self._scanner_lbl.setStyleSheet('color: #64748B; font-size: 10px; padding: 0 8px;')
        self.addWidget(self._scanner_lbl)

        self._sep1 = QLabel('|')
        self._sep1.setStyleSheet('color: #2D3748;')
        self.addWidget(self._sep1)

        self._last_scan_lbl = QLabel('Last Scan: —')
        self._last_scan_lbl.setStyleSheet('color: #4B5563; font-size: 10px; padding: 0 8px;')
        self.addWidget(self._last_scan_lbl)

        # Right side
        self._alerts_lbl = QLabel('Alerts: 0')
        self._alerts_lbl.setStyleSheet('color: #4B5563; font-size: 10px; padding: 0 8px;')
        self.addPermanentWidget(self._alerts_lbl)

        hint_lbl = QLabel('F5 Refresh   Ctrl+, Settings   Ctrl+A Alerts')
        hint_lbl.setStyleSheet('color: #374151; font-size: 9px; padding: 0 8px;')
        self.addPermanentWidget(hint_lbl)

    def set_scanner_active(self, active: bool) -> None:
        if active:
            self._scanner_lbl.setText('● Scanner Running')
            self._scanner_lbl.setStyleSheet('color: #22C55E; font-size: 10px; padding: 0 8px;')
        else:
            self._scanner_lbl.setText('● Scanner Idle')
            self._scanner_lbl.setStyleSheet('color: #64748B; font-size: 10px; padding: 0 8px;')

    def set_status_message(self, message: str) -> None:
        self._last_scan_lbl.setText(message)

    def set_alert_count(self, count: int) -> None:
        color = '#F59E0B' if count > 0 else '#4B5563'
        self._alerts_lbl.setText(f'Alerts: {count}')
        self._alerts_lbl.setStyleSheet(f'color: {color}; font-size: 10px; padding: 0 8px; font-weight: {700 if count else 400};')
