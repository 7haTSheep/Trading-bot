"""
AnalysisWindow.py — Detailed 14-point institutional analysis popup dialog / panel.

When a user selects a symbol in the scanner table, this window presents:
  1. Trade Decision Header (Decision Badge, Grade, Quality Score, Confidence)
  2. Actionable Setup Checklist (PASS/FAIL/WARN)
  3. Dynamic Risk & Position Sizing Panel (Stop Loss, Lot Size, Risk $)
  4. Multi-Target Profit Targets Table (TP1, TP2, TP3 with R:R and Probabilities)
  5. Chart Marking Coordinates (Exact lines to place on MT5 chart)
  6. Setup Invalidation Criteria & Wait Conditions
  7. Interactive Candlestick Chart (ChartWidget)
"""
from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QGroupBox, QScrollArea, QWidget, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from App.UI.Widgets.DecisionBadge import DecisionBadge
from App.UI.Widgets.GradeLabel import GradeLabel
from App.UI.Widgets.ChecklistWidget import ChecklistWidget
from App.UI.Chart.ChartWidget import ChartWidget


class AnalysisWindow(QDialog):
    """Deep-dive institutional analysis modal/dock window for a single symbol."""

    def __init__(self, result: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self._result = result
        self.setWindowTitle(f"Institutional Analysis — {result.get('symbol', 'Symbol')}")
        self.resize(1100, 750)
        self._build_ui()
        self.load_result(result)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ------------------------------------------------------------------
        # Header Box (Decision, Grade, Quality Score)
        # ------------------------------------------------------------------
        hdr = QFrame()
        hdr.setProperty('role', 'panel')
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(16, 12, 16, 12)

        # Symbol & Price
        sym_box = QVBoxLayout()
        self._sym_lbl = QLabel('—')
        self._sym_lbl.setStyleSheet('font-size: 22px; font-weight: 900; color: #F1F5F9;')
        self._price_lbl = QLabel('Bid: —  |  Spread: —')
        self._price_lbl.setStyleSheet('font-size: 11px; color: #64748B;')
        sym_box.addWidget(self._sym_lbl)
        sym_box.addWidget(self._price_lbl)
        hdr_layout.addLayout(sym_box)

        hdr_layout.addStretch()

        # Grade
        self._grade_lbl = GradeLabel('—')
        hdr_layout.addWidget(self._grade_lbl)

        # Decision Badge
        self._decision_badge = DecisionBadge('—')
        hdr_layout.addWidget(self._decision_badge)

        # Quality Score
        q_box = QVBoxLayout()
        q_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_val = QLabel('0%')
        self._score_val.setStyleSheet('font-size: 20px; font-weight: 900; color: #3B82F6;')
        q_lbl = QLabel('QUALITY SCORE')
        q_lbl.setStyleSheet('font-size: 9px; color: #64748B; font-weight: 600;')
        q_box.addWidget(self._score_val)
        q_box.addWidget(q_lbl)
        hdr_layout.addLayout(q_box)

        root.addWidget(hdr)

        # ------------------------------------------------------------------
        # Splitter: Left Panel (Metrics & Checklist) vs Right Panel (Chart)
        # ------------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT: Analysis Notebook ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        # Tab 1: Trade Engine & Risk
        tab_trade = QWidget()
        tt_layout = QVBoxLayout(tab_trade)

        # Wait / Invalidation box
        inval_box = QGroupBox('TRADE CONDITIONS & INVALIDATION')
        ib_layout = QVBoxLayout(inval_box)
        self._wait_lbl = QLabel('Waiting for: None')
        self._wait_lbl.setStyleSheet('color: #F59E0B; font-weight: 600;')
        self._inval_lbl = QLabel('Invalidation: —')
        self._inval_lbl.setStyleSheet('color: #EF4444;')
        ib_layout.addWidget(self._wait_lbl)
        ib_layout.addWidget(self._inval_lbl)
        tt_layout.addWidget(inval_box)

        # Risk & Targets Table
        tp_box = QGroupBox('PROFIT TARGETS & RISK MANAGEMENT')
        tp_layout = QVBoxLayout(tp_box)

        self._risk_info_lbl = QLabel('Stop Loss: —  |  Lot Size: —  |  Risk Amount: —')
        self._risk_info_lbl.setStyleSheet('font-weight: 600; color: #F1F5F9; font-size: 11px;')
        tp_layout.addWidget(self._risk_info_lbl)

        self._tp_table = QTableWidget(3, 4)
        self._tp_table.setHorizontalHeaderLabels(['Target', 'Price', 'R:R Ratio', 'Probability'])
        self._tp_table.horizontalHeader().setStretchLastSection(True)
        self._tp_table.setFixedHeight(120)
        tp_layout.addWidget(self._tp_table)

        tt_layout.addWidget(tp_box)

        # Chart Markings Table
        m_box = QGroupBox('REQUIRED CHART MARKINGS (MT5)')
        m_layout = QVBoxLayout(m_box)
        self._markings_table = QTableWidget(0, 3)
        self._markings_table.setHorizontalHeaderLabels(['Level Label', 'Exact Price', 'Line Color'])
        self._markings_table.horizontalHeader().setStretchLastSection(True)
        self._markings_table.setFixedHeight(120)
        m_layout.addWidget(self._markings_table)
        tt_layout.addWidget(m_box)

        tabs.addTab(tab_trade, 'Trade Decision & Levels')

        # Tab 2: Setup Checklist
        tab_check = QWidget()
        tc_layout = QVBoxLayout(tab_check)
        self._checklist = ChecklistWidget()
        scroll = QScrollArea()
        scroll.setWidget(self._checklist)
        scroll.setWidgetResizable(True)
        tc_layout.addWidget(scroll)
        tabs.addTab(tab_check, 'Institutional Checklist')

        left_layout.addWidget(tabs)
        splitter.addWidget(left_widget)

        # --- RIGHT: Interactive Chart ---
        self._chart = ChartWidget()
        splitter.addWidget(self._chart)

        splitter.setSizes([450, 650])
        root.addWidget(splitter)

        # Close button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton('Close Analysis')
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        root.addLayout(btn_box)

    # ------------------------------------------------------------------
    # Data Population
    # ------------------------------------------------------------------
    def load_result(self, result: Dict[str, Any]) -> None:
        sym = result.get('symbol', '—')
        bid = result.get('bid', 0.0)
        spread = result.get('spread', 0.0)
        self._sym_lbl.setText(sym)
        self._price_lbl.setText(f'Bid: {bid:,.4f}  |  Spread: {spread:,.1f}')

        dp = result.get('decision_panel', {})
        decision = dp.get('decision', '—')
        grade = dp.get('grade', '—')
        quality = dp.get('entry_quality_score', 0)

        self._decision_badge.set_decision(decision)
        self._grade_lbl.set_grade(grade)
        self._score_val.setText(f'{quality}%')

        # Wait / Invalidation
        waits = dp.get('waiting_for', [])
        wait_str = ', '.join(waits) if waits else 'None (Setup Ready)'
        self._wait_lbl.setText(f'Waiting for: {wait_str}')
        self._inval_lbl.setText(f"Invalidation: {dp.get('invalidation', 'N/A')}")

        # Risk
        rp = result.get('risk_panel', {})
        stop = rp.get('stop_loss', 0.0)
        lots = rp.get('lot_size', 0.0)
        risk_amt = rp.get('risk_amount', 0.0)
        self._risk_info_lbl.setText(f'Stop Loss: {stop:,.4f}  |  Lot Size: {lots:.2f} lots  |  Risk: ${risk_amt:,.2f}')

        # Targets
        targets = rp.get('profit_targets', [])
        for row, t in enumerate(targets[:3]):
            self._tp_table.setItem(row, 0, QTableWidgetItem(t.get('label', '')))
            self._tp_table.setItem(row, 1, QTableWidgetItem(f"{t.get('price', 0.0):,.4f}"))
            self._tp_table.setItem(row, 2, QTableWidgetItem(f"{t.get('rr', 0.0):.1f}:1"))
            self._tp_table.setItem(row, 3, QTableWidgetItem(t.get('hit_probability', 'Medium')))

        # Markings
        markings = result.get('chart_panel', {}).get('markings', [])
        self._markings_table.setRowCount(len(markings))
        for row, m in enumerate(markings):
            self._markings_table.setItem(row, 0, QTableWidgetItem(m.get('label', '')))
            self._markings_table.setItem(row, 1, QTableWidgetItem(f"{m.get('price', 0.0):,.4f}"))
            self._markings_table.setItem(row, 2, QTableWidgetItem(m.get('color', '#3B82F6')))

        # Checklist
        chk_items = result.get('checklist', {}).get('items', [])
        self._checklist.load(chk_items)

        # Chart
        self._chart.load_data(sym, markings=markings)
