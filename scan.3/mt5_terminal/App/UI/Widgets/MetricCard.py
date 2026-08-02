"""
MetricCard.py — Reusable metric display card for the dashboard.
"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class MetricCard(QFrame):
    """A mini dashboard card showing a titled metric value."""

    def __init__(
        self,
        title: str,
        value: str = '—',
        unit: str = '',
        accent_color: str = '#3B82F6',
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty('role', 'card')
        self.setMinimumWidth(140)
        self._accent = accent_color
        self._build_ui(title, value, unit)

    def _build_ui(self, title: str, value: str, unit: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        # Accent bar
        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f'background-color: {self._accent}; border-radius: 2px;')
        layout.addWidget(bar)

        layout.addSpacing(4)

        # Title
        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setProperty('role', 'muted')
        self._title_lbl.setStyleSheet('font-size: 9px; letter-spacing: 0.08em; font-weight: 600; color: #4B5563;')
        layout.addWidget(self._title_lbl)

        # Value row
        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        self._value_lbl = QLabel(value)
        self._value_lbl.setProperty('role', 'value')
        self._value_lbl.setStyleSheet(
            f'font-size: 20px; font-weight: 700; color: #F1F5F9; '
            f'font-family: "Consolas", monospace;'
        )
        value_row.addWidget(self._value_lbl)

        if unit:
            self._unit_lbl = QLabel(unit)
            self._unit_lbl.setStyleSheet('font-size: 11px; color: #4B5563; padding-top: 8px;')
            value_row.addWidget(self._unit_lbl)

        value_row.addStretch()
        layout.addLayout(value_row)

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self._value_lbl.setText(value)

    def set_accent(self, color: str) -> None:
        self._accent = color
        self.update()
