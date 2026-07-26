"""
DashboardWidget.py — Account overview dashboard shown at the top of the main window.
"""
from __future__ import annotations
import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from App.UI.Widgets.MetricCard import MetricCard


class DashboardWidget(QWidget):
    """Top bar showing account health and scanner status at a glance."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setObjectName('DashboardWidget')
        self._build_ui()
        self._start_clock()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(12)

        # Logo / Title
        logo_frame = QFrame()
        logo_frame.setFixedWidth(180)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(2)

        title = QLabel('MT5 TERMINAL')
        title.setStyleSheet(
            'font-size: 16px; font-weight: 900; color: #F1F5F9; '
            'letter-spacing: 0.08em;'
        )
        subtitle = QLabel('Institutional Scanner')
        subtitle.setStyleSheet('font-size: 10px; color: #3B82F6; font-weight: 600;')
        logo_layout.addWidget(title)
        logo_layout.addWidget(subtitle)
        logo_layout.addStretch()

        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet(
            'font-size: 11px; color: #64748B; font-family: "Consolas", monospace;'
        )
        logo_layout.addWidget(self._clock_lbl)
        root.addWidget(logo_frame)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet('color: #2D3748;')
        root.addWidget(sep)

        # Metric Cards
        self._balance_card  = MetricCard('Balance',      '—',   'USD', '#22C55E')
        self._equity_card   = MetricCard('Equity',       '—',   'USD', '#3B82F6')
        self._margin_card   = MetricCard('Margin Level', '—',   '%',   '#6366F1')
        self._pnl_card      = MetricCard('Floating P&L', '—',   'USD', '#F59E0B')
        self._scans_card    = MetricCard('Active Scans', '0',   '',    '#22C55E')

        for card in (
            self._balance_card, self._equity_card,
            self._margin_card, self._pnl_card, self._scans_card
        ):
            root.addWidget(card)

        root.addStretch()

        # Connection Status
        self._conn_frame = QFrame()
        self._conn_frame.setProperty('role', 'card')
        self._conn_frame.setFixedWidth(140)
        conn_layout = QVBoxLayout(self._conn_frame)
        conn_layout.setContentsMargins(12, 8, 12, 8)

        conn_title = QLabel('MT5 STATUS')
        conn_title.setStyleSheet(
            'font-size: 9px; color: #4B5563; letter-spacing: 0.08em; font-weight: 600;'
        )
        self._conn_dot = QLabel('● DISCONNECTED')
        self._conn_dot.setStyleSheet('font-size: 11px; color: #EF4444; font-weight: 700;')
        self._conn_server = QLabel('—')
        self._conn_server.setStyleSheet('font-size: 9px; color: #4B5563;')

        conn_layout.addWidget(conn_title)
        conn_layout.addWidget(self._conn_dot)
        conn_layout.addWidget(self._conn_server)
        root.addWidget(self._conn_frame)

    def update_account(self, info: dict) -> None:
        balance = info.get('balance', 0)
        equity  = info.get('equity',  0)
        margin  = info.get('margin_level', 0)
        profit  = info.get('profit',  0)
        server  = info.get('server', '—')

        self._balance_card.set_value(f'{balance:,.2f}')
        self._equity_card.set_value(f'{equity:,.2f}')
        self._margin_card.set_value(f'{margin:.1f}')

        pnl_color = '#22C55E' if profit >= 0 else '#EF4444'
        sign = '+' if profit >= 0 else ''
        self._pnl_card.set_value(f'{sign}{profit:,.2f}')
        self._pnl_card._value_lbl.setStyleSheet(
            f'font-size: 20px; font-weight: 700; color: {pnl_color}; '
            f'font-family: "Consolas", monospace;'
        )

        self._conn_dot.setText('● CONNECTED')
        self._conn_dot.setStyleSheet('font-size: 11px; color: #22C55E; font-weight: 700;')
        self._conn_server.setText(server)

    def update_scan_count(self, count: int) -> None:
        self._scans_card.set_value(str(count))

    def set_disconnected(self) -> None:
        self._conn_dot.setText('● DISCONNECTED')
        self._conn_dot.setStyleSheet('font-size: 11px; color: #EF4444; font-weight: 700;')
        self._conn_server.setText('—')

    def _start_clock(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        now = datetime.datetime.utcnow()
        self._clock_lbl.setText(now.strftime('UTC  %Y-%m-%d  %H:%M:%S'))
