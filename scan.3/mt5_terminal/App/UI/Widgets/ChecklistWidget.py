"""
ChecklistWidget.py — Setup checklist panel showing PASS/FAIL/WARN for each
institutional condition.
"""
from __future__ import annotations
from typing import List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt

_STATUS_STYLE = {
    'PASS': ('#22C55E', '✓'),
    'FAIL': ('#EF4444', '✗'),
    'WARN': ('#F59E0B', '⚠'),
    'N/A':  ('#64748B', '—'),
}


class _CheckItem(QFrame):
    def __init__(self, name: str, status: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty('role', 'inset')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        color, icon = _STATUS_STYLE.get(status.upper(), ('#64748B', '—'))
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet(f'color: {color}; font-size: 13px; font-weight: 700;')
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet('color: #94A3B8; font-size: 11px;')
        layout.addWidget(name_lbl)
        layout.addStretch()

        status_lbl = QLabel(status.upper())
        status_lbl.setStyleSheet(f'color: {color}; font-size: 10px; font-weight: 600;')
        layout.addWidget(status_lbl)


class ChecklistWidget(QWidget):
    """Renders a vertical list of condition check items."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)

    def load(self, items: List[Dict[str, str]]) -> None:
        """items: [{'name': str, 'status': 'PASS'|'FAIL'|'WARN'}, ...]"""
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for item in items:
            self._layout.addWidget(_CheckItem(item['name'], item['status']))
