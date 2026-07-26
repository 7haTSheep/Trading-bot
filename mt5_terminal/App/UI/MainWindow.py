"""
MainWindow.py — Main QMainWindow shell for MT5 Institutional Terminal.

Assembles all application layers:
  - Top: DashboardWidget (Account & Status)
  - Center: ScannerPanel (Live Watchlist Table) + Right Chart/Analysis dock
  - Bottom: StatusBarWidget
  - Controller: ScannerController QThread worker
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QDockWidget, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence

from App.Services.LogService import log_service
from App.Services.MT5Service import MT5Service
from App.Services.DatabaseService import DatabaseService
from App.Core.Scanner.ScannerController import ScannerController

from App.UI.Dashboard.DashboardWidget import DashboardWidget
from App.UI.Dashboard.StatusBarWidget import StatusBarWidget
from App.UI.Scanner.ScannerPanel import ScannerPanel
from App.UI.Analysis.AnalysisWindow import AnalysisWindow
from App.UI.Settings.SettingsDialog import SettingsDialog
from App.UI.Chart.ChartWidget import ChartWidget

_log = log_service.get('app')
CONFIG_PATH = Path(__file__).resolve().parents[3] / 'Configs' / 'settings.json'


class MainWindow(QMainWindow):
    """Primary application window for MT5 Terminal."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('MetaTrader 5 — Institutional Trade Terminal')
        self.resize(1400, 900)

        self._mt5 = MT5Service()
        self._db = DatabaseService()
        self._load_config()

        self._build_menu()
        self._build_ui()
        self._init_backend()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self._cfg = json.load(f)
        else:
            self._cfg = {
                'symbols': ['Volatility 75 (1s) Index', 'Volatility 25 Index', 'EURUSD'],
                'scan_interval_seconds': 30,
                'risk_percent': 5.0,
            }

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu('&File')

        settings_act = QAction('&Settings…', self)
        settings_act.setShortcut(QKeySequence('Ctrl+,'))
        settings_act.triggered.connect(self._open_settings)
        file_menu.addAction(settings_act)

        file_menu.addSeparator()

        exit_act = QAction('E&xit', self)
        exit_act.setShortcut(QKeySequence('Ctrl+Q'))
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Scanner Menu
        scan_menu = menubar.addMenu('&Scanner')

        start_act = QAction('&Start Scanner', self)
        start_act.triggered.connect(self._start_scanner)
        scan_menu.addAction(start_act)

        stop_act = QAction('S&top Scanner', self)
        stop_act.triggered.connect(self._stop_scanner)
        scan_menu.addAction(stop_act)

        # Help Menu
        help_menu = menubar.addMenu('&Help')
        about_act = QAction('&About MT5 Terminal', self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Dashboard Header
        self._dashboard = DashboardWidget()
        main_layout.addWidget(self._dashboard)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Scanner Table
        self._scanner_panel = ScannerPanel()
        self._scanner_panel.row_selected.connect(self._on_row_selected)
        self._scanner_panel._refresh_btn.clicked.connect(self._manual_scan)
        splitter.addWidget(self._scanner_panel)

        # Right: Quick Chart Preview
        self._preview_chart = ChartWidget()
        splitter.addWidget(self._preview_chart)

        splitter.setSizes([750, 650])
        main_layout.addWidget(splitter)

        # Bottom Status Bar
        self._status_bar = StatusBarWidget()
        self.setStatusBar(self._status_bar)

    # ------------------------------------------------------------------
    # Backend & Controller Wiring
    # ------------------------------------------------------------------
    def _init_backend(self) -> None:
        # Try connecting to MT5
        connected = self._mt5.connect()
        if connected:
            acc_info = self._mt5.get_account_info()
            self._dashboard.update_account(acc_info)
        else:
            self._dashboard.set_disconnected()

        # Initialize Scanner Controller
        symbols = self._cfg.get('symbols', ['Volatility 75 (1s) Index'])
        interval = self._cfg.get('scan_interval_seconds', 30)
        risk = self._cfg.get('risk_percent', 5.0)

        self._controller = ScannerController(symbols, interval, risk, parent=self)
        self._controller.result_ready.connect(self._on_scan_result)
        self._controller.status_changed.connect(self._status_bar.set_status_message)
        self._controller.scanner_state_changed.connect(self._status_bar.set_scanner_active)

        # Auto-start scanner
        self._controller.start()

        # Account Poller Timer (refresh balance every 5s)
        self._acc_timer = QTimer(self)
        self._acc_timer.timeout.connect(self._refresh_account)
        self._acc_timer.start(5000)

    # ------------------------------------------------------------------
    # Event Handlers & Slots
    # ------------------------------------------------------------------
    @Slot(dict)
    def _on_scan_result(self, result: dict) -> None:
        """Received from ScannerController QThread."""
        self._scanner_panel.on_result(result)
        self._db.insert_scan(result)
        self._dashboard.update_scan_count(len(self._scanner_panel._results))

    @Slot(dict)
    def _on_row_selected(self, result: dict) -> None:
        """User selected a symbol row — update preview chart and open deep-dive dialog."""
        sym = result.get('symbol', '—')
        markings = result.get('chart_panel', {}).get('markings', [])
        self._preview_chart.load_data(sym, markings=markings)

        # Open full analysis modal
        dlg = AnalysisWindow(result, parent=self)
        dlg.exec()

    def _refresh_account(self) -> None:
        if self._mt5.is_connected:
            info = self._mt5.get_account_info()
            if info:
                self._dashboard.update_account(info)

    def _manual_scan(self) -> None:
        _log.info('Manual scan triggered')
        if not self._controller.is_running:
            self._controller.start()

    def _start_scanner(self) -> None:
        self._controller.start()

    def _stop_scanner(self) -> None:
        self._controller.stop()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(parent=self)
        if dlg.exec():
            self._load_config()
            self._controller.set_symbols(self._cfg.get('symbols', []))
            self._controller.set_interval(self._cfg.get('scan_interval_seconds', 30))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            'About MT5 Terminal',
            '<b>MetaTrader 5 Institutional Trade Terminal</b><br>'
            'Version 2.0.0<br><br>'
            'Commercial-grade trade decision engine & scanner for MT5 synthetic indices and FX.'
        )

    def closeEvent(self, event) -> None:
        _log.info('Shutting down MT5 Terminal...')
        self._controller.stop()
        self._mt5.disconnect()
        event.accept()
