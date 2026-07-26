"""
ScannerPanel.py — Main scanner table panel.

Shows every watched symbol as a row with columns:
  Symbol | Bid | Spread | Decision | Grade | Quality | Bias | Last Update

Clicking a row opens AnalysisWindow for a deep dive.
The table auto-refreshes when the ScannerController emits result_ready.
"""
from __future__ import annotations
from typing import Optional
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QFrame, QSizePolicy,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QTimer
from PySide6.QtGui import QColor, QFont, QBrush

from App.UI.Widgets.DecisionBadge import DecisionBadge
from App.UI.Widgets.GradeLabel import GradeLabel


# Column indices
COL_SYMBOL   = 0
COL_BID      = 1
COL_SPREAD   = 2
COL_DECISION = 3
COL_GRADE    = 4
COL_QUALITY  = 5
COL_BIAS     = 6
COL_UPDATED  = 7
_HEADERS = ['Symbol', 'Bid', 'Spread', 'Decision', 'Grade', 'Quality%', 'Bias', 'Updated']

_DECISION_COLORS = {
    'ENTER LONG':  '#22C55E',
    'ENTER SHORT': '#EF4444',
    'WAIT':        '#F59E0B',
    'SKIP':        '#64748B',
    'NO TRADE':    '#64748B',
}


class ScannerPanel(QWidget):
    """
    Main scanner panel — sortable/filterable table of scan results.

    Signals:
        row_selected(dict): emitted when user clicks a row (full result dict).
    """

    row_selected = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._results: dict[str, dict] = {}   # symbol → result dict
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Toolbar ---
        toolbar = QFrame()
        toolbar.setObjectName('ScannerToolbar')
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(
            'QFrame#ScannerToolbar { '
            'background-color: #0D1321; '
            'border-bottom: 1px solid #2D3748; }'
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(8)

        # Section title
        title_lbl = QLabel('SCANNER')
        title_lbl.setStyleSheet(
            'font-size: 11px; font-weight: 700; color: #64748B; '
            'letter-spacing: 0.1em;'
        )
        tb_layout.addWidget(title_lbl)

        tb_layout.addSpacing(8)

        # Search box
        self._search = QLineEdit()
        self._search.setPlaceholderText('Filter symbols…')
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)
        tb_layout.addWidget(self._search)

        tb_layout.addStretch()

        # Count label
        self._count_lbl = QLabel('0 symbols')
        self._count_lbl.setStyleSheet('font-size: 10px; color: #4B5563;')
        tb_layout.addWidget(self._count_lbl)

        # Refresh button
        self._refresh_btn = QPushButton('⟳  Scan Now')
        self._refresh_btn.setProperty('role', 'primary')
        self._refresh_btn.setFixedHeight(30)
        tb_layout.addWidget(self._refresh_btn)

        root.addWidget(toolbar)

        # --- Table ---
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            COL_SYMBOL, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(COL_SYMBOL, 220)
        self._table.setColumnWidth(COL_BID,    110)
        self._table.setColumnWidth(COL_SPREAD,  70)
        self._table.setColumnWidth(COL_DECISION,180)
        self._table.setColumnWidth(COL_GRADE,   60)
        self._table.setColumnWidth(COL_QUALITY,  80)
        self._table.setColumnWidth(COL_BIAS,    100)
        self._table.setRowHeight(0, 40)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        self._table.clicked.connect(self._on_single_click)

        root.addWidget(self._table)

    # ------------------------------------------------------------------
    # Public API — called by MainWindow when ScannerController emits
    # ------------------------------------------------------------------
    def on_result(self, result: dict) -> None:
        """Upsert a scan result row for the given symbol."""
        symbol = result.get('symbol', '?')
        self._results[symbol] = result
        self._upsert_row(symbol, result)
        self._count_lbl.setText(f'{len(self._results)} symbols')

    def _upsert_row(self, symbol: str, result: dict) -> None:
        # Check if row exists
        existing_row = None
        for row in range(self._table.rowCount()):
            item = self._table.item(row, COL_SYMBOL)
            if item and item.text() == symbol:
                existing_row = row
                break

        if existing_row is None:
            self._table.insertRow(0)
            existing_row = 0
            self._table.setRowHeight(0, 40)

        self._populate_row(existing_row, symbol, result)

    def _populate_row(self, row: int, symbol: str, result: dict) -> None:
        dp = result.get('decision_panel', {})
        decision = dp.get('decision', '—')
        grade    = dp.get('grade', '—')
        quality  = dp.get('entry_quality_score', 0)
        sm       = result.get('summary', {})
        bias     = sm.get('bias', '—')
        bid      = result.get('bid', 0.0)
        spread   = result.get('spread', 0.0)
        updated  = datetime.datetime.now().strftime('%H:%M:%S')

        def _item(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
            it = QTableWidgetItem(text)
            it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return it

        self._table.setItem(row, COL_SYMBOL,  _item(symbol))
        self._table.setItem(row, COL_BID,     _item(f'{bid:,.4f}', Qt.AlignmentFlag.AlignRight))
        self._table.setItem(row, COL_SPREAD,  _item(f'{spread:,.1f}', Qt.AlignmentFlag.AlignRight))

        # Decision — colour coded
        dec_item = _item(decision, Qt.AlignmentFlag.AlignCenter)
        dec_color = '#F1F5F9'
        for key, col in _DECISION_COLORS.items():
            if key in decision.upper():
                dec_color = col
                break
        dec_item.setForeground(QBrush(QColor(dec_color)))
        font = dec_item.font()
        font.setBold(True)
        dec_item.setFont(font)
        self._table.setItem(row, COL_DECISION, dec_item)

        # Grade
        grade_item = _item(grade, Qt.AlignmentFlag.AlignCenter)
        grade_colors = {'A': '#22C55E', 'B': '#3B82F6', 'C': '#F59E0B', 'D': '#EF4444'}
        grade_item.setForeground(QBrush(QColor(grade_colors.get(grade, '#94A3B8'))))
        gf = grade_item.font()
        gf.setBold(True)
        gf.setPointSize(12)
        grade_item.setFont(gf)
        self._table.setItem(row, COL_GRADE, grade_item)

        # Quality %
        q_item = _item(f'{quality}%', Qt.AlignmentFlag.AlignCenter)
        q_color = '#22C55E' if quality >= 70 else '#F59E0B' if quality >= 50 else '#EF4444'
        q_item.setForeground(QBrush(QColor(q_color)))
        self._table.setItem(row, COL_QUALITY, q_item)

        # Bias
        bias_item = _item(bias, Qt.AlignmentFlag.AlignCenter)
        bias_color = '#22C55E' if 'bull' in bias.lower() else '#EF4444' if 'bear' in bias.lower() else '#64748B'
        bias_item.setForeground(QBrush(QColor(bias_color)))
        self._table.setItem(row, COL_BIAS, bias_item)

        self._table.setItem(row, COL_UPDATED, _item(updated, Qt.AlignmentFlag.AlignCenter))

        # Store result in first item for retrieval
        self._table.item(row, COL_SYMBOL).setData(Qt.ItemDataRole.UserRole, result)

    def _apply_filter(self, text: str) -> None:
        text = text.lower()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, COL_SYMBOL)
            if item:
                self._table.setRowHidden(row, text not in item.text().lower())

    def _on_single_click(self, index) -> None:
        row = index.row()
        item = self._table.item(row, COL_SYMBOL)
        if item:
            result = item.data(Qt.ItemDataRole.UserRole)
            if result:
                self.row_selected.emit(result)

    def _on_double_click(self, item) -> None:
        """Same as single click — AnalysisWindow opens on single click from MainWindow."""
        pass
