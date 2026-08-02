"""
DecisionBadge.py — Colour-coded decision status badge.
"""
from __future__ import annotations
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

_STYLE_MAP = {
    'ENTER LONG': ('badge-enter-long', '#22C55E'),
    'ENTER SHORT': ('badge-enter-short', '#EF4444'),
    'WAIT': ('badge-wait', '#F59E0B'),
    'SKIP': ('badge-skip', '#64748B'),
    'NO TRADE': ('badge-skip', '#64748B'),
    'DEFAULT': ('badge-wait', '#F59E0B'),
}


class DecisionBadge(QLabel):
    """Visual badge displaying the current trade decision."""

    def __init__(self, decision: str = '—', parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_decision(decision)

    def set_decision(self, decision: str) -> None:
        role_key = 'DEFAULT'
        for key in _STYLE_MAP:
            if key in decision.upper():
                role_key = key
                break

        role, color = _STYLE_MAP[role_key]
        self.setText(decision)
        self.setStyleSheet(
            f'background-color: {color}22; '
            f'color: {color}; '
            f'border: 1px solid {color}66; '
            f'border-radius: 4px; '
            f'padding: 4px 12px; '
            f'font-weight: 700; '
            f'font-size: 11px;'
        )
