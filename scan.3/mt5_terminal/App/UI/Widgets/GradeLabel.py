"""
GradeLabel.py — A/B/C/D grade display widget with colour coding.
"""
from __future__ import annotations
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

_GRADE_COLORS = {
    'A': ('#22C55E', '#052E16'),
    'B': ('#3B82F6', '#072448'),
    'C': ('#F59E0B', '#3B1A00'),
    'D': ('#EF4444', '#3A0505'),
}


class GradeLabel(QLabel):
    """Large grade letter badge."""

    def __init__(self, grade: str = '—', parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(36, 36)
        self.set_grade(grade)

    def set_grade(self, grade: str) -> None:
        fg, bg = _GRADE_COLORS.get(grade.upper(), ('#64748B', '#1A2236'))
        self.setText(grade)
        self.setStyleSheet(
            f'background-color: {bg}; '
            f'color: {fg}; '
            f'border: 2px solid {fg}; '
            f'border-radius: 6px; '
            f'font-size: 18px; '
            f'font-weight: 900;'
        )
