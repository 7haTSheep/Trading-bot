"""QuickScan — a windowed front end for the scanner.

Everything the command line does, without the command line: pick symbols,
set risk, press Start, watch the reports arrive.

The scanning itself is the same code the CLI runs (quickscan.scan_symbol),
called on a worker thread with its printed output captured, so the window
cannot show something different from what the scanner actually produced.

All MetaTrader calls happen on that one worker thread. The MT5 package is
global, process-wide state, and calling it from both the GUI thread and a
worker is a good way to get answers that belong to the other caller.

    python quickscan_app.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

import theme
from surface import ReportHighlighter, TextureBackdrop
from trades_view import TradesTab

TIMEFRAMES = [('1 minute', '1m'), ('5 minutes', '5m'), ('15 minutes', '15m'),
              ('30 minutes', '30m'), ('1 hour', '1h'), ('4 hours', '4h')]


def _section(text: str) -> QLabel:
    """A small capitalised heading. Qt stylesheets have no text-transform,
    so the capitals are applied here rather than in the stylesheet."""
    label = QLabel(text.upper())
    label.setObjectName('SectionLabel')
    return label


class ScannerWorker(QThread):
    """Runs the scanner off the GUI thread and reports back by signal."""

    output = Signal(str)
    account = Signal(str, str, float, bool)   # login, server, equity, is_demo
    state = Signal(str)
    history = Signal(list)
    finished_cleanly = Signal()

    def __init__(self, symbols: List[str], risk: float, stop_atr: float, timeframe: str):
        super().__init__()
        self.symbols = symbols
        self.risk = risk
        self.stop_atr = stop_atr
        self.timeframe = timeframe
        self._stop = False
        self._history_days: Optional[int] = None

    def stop(self):
        self._stop = True

    def request_history(self, days: int):
        """Ask for trade history on the next loop.

        The scan owns the MetaTrader connection while it runs, and that
        connection is process-wide, so a second thread must not read history
        behind its back. Serving the request from this thread keeps every MT5
        call on one thread, which is the rule the rest of this file follows.
        """
        self._history_days = days

    def run(self):
        try:
            import MetaTrader5 as mt5
            import quickscan
            from candle_monitor import CandleMonitor, timeframe_spec
        except Exception as exc:
            self.output.emit(f'Could not load the scanner: {exc}\n')
            self.finished_cleanly.emit()
            return

        if not mt5.initialize():
            self.output.emit('Could not reach MetaTrader 5.\n\n'
                             'Open MetaTrader 5, log into your account, then press Start again.\n')
            self.finished_cleanly.emit()
            return

        try:
            info = mt5.account_info()
            if info is not None:
                self.account.emit(str(info.login), info.server, info.equity,
                                  info.trade_mode == 0)
            equity = info.equity if info else None

            spec = timeframe_spec(self.timeframe, mt5)
            monitors = {s: CandleMonitor(mt5, s, spec) for s in self.symbols}
            for monitor in monitors.values():
                monitor.initialize()

            self.state.emit(f'Scanning {len(self.symbols)} symbol(s) on {spec["label"]}')
            self._scan_all(quickscan, equity)

            while not self._stop:
                if self._history_days is not None:
                    days, self._history_days = self._history_days, None
                    self._emit_history(days)
                due = [s for s, m in monitors.items() if m.new_closed_candle() is not None]
                if due:
                    self.output.emit(f'\n{"=" * 70}\nNew {spec["label"]} candle closed\n{"=" * 70}\n')
                    self._scan_all(quickscan, equity, due)
                else:
                    remaining = next(iter(monitors.values())).seconds_remaining()
                    if remaining is not None:
                        self.state.emit(f'Next {spec["label"]} close in '
                                        f'{CandleMonitor.format_countdown(remaining)}')
                # Short sleeps so Stop is responsive rather than waiting a full poll.
                for _ in range(10):
                    if self._stop:
                        break
                    time.sleep(0.1)
        except Exception as exc:
            self.output.emit(f'\nThe scan stopped unexpectedly: {exc}\n')
        finally:
            mt5.shutdown()
            self.state.emit('Stopped')
            self.finished_cleanly.emit()

    def _emit_history(self, days: int):
        try:
            import MetaTrader5 as mt5
            import trades
            self.history.emit(trades.load_trades(mt5, days))
        except Exception as exc:
            self.output.emit(f'\nCould not read trade history: {exc}\n')
            self.history.emit([])

    def _scan_all(self, quickscan, equity, symbols: Optional[List[str]] = None):
        due = symbols if symbols is not None else self.symbols
        # scan_symbol appends a row here per symbol; the master summary table
        # is built from them once the pass is done, exactly as the CLI does it.
        summary_rows: list = []
        for symbol in due:
            if self._stop:
                return
            self.state.emit(f'Scanning {symbol}')
            # scan_symbol prints its report; capturing it keeps the window and
            # the command line showing exactly the same thing.
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    quickscan.scan_symbol(symbol, self.risk, self.stop_atr, equity,
                                          summary_rows=summary_rows)
            except Exception as exc:
                buffer.write(f'\n{symbol}: could not be scanned ({exc})\n')
            self.output.emit(buffer.getvalue())

        # One symbol has nothing to compare against, and its own report already
        # ends with the same numbers. Matches the CLI's rule.
        if len(summary_rows) > 1 and not self._stop:
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    quickscan.print_master_summary(summary_rows)
            except Exception as exc:
                buffer.write(f'\nCould not build the summary table: {exc}\n')
            self.output.emit(buffer.getvalue())


class SymbolLoader(QThread):
    """Fetches the tradable symbol list without freezing the window."""

    loaded = Signal(list, str)

    def run(self):
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                self.loaded.emit([], 'MetaTrader 5 is not running, or not logged in.')
                return
            try:
                names = sorted(s.name for s in (mt5.symbols_get() or []))
            finally:
                mt5.shutdown()
            self.loaded.emit(names, '' if names else 'No symbols were returned.')
        except Exception as exc:
            self.loaded.emit([], str(exc))


class HistoryLoader(QThread):
    """Reads closed trades when no scan is running and owns the connection."""

    loaded = Signal(list, str)

    def __init__(self, days: int):
        super().__init__()
        self.days = days

    def run(self):
        try:
            import MetaTrader5 as mt5
            import trades
            if not mt5.initialize():
                self.loaded.emit([], 'MetaTrader 5 is not running, or not logged in.')
                return
            try:
                rows = trades.load_trades(mt5, self.days)
            finally:
                mt5.shutdown()
            self.loaded.emit(rows, '')
        except Exception as exc:
            self.loaded.emit([], str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('QuickScan')
        self.resize(1180, 790)
        self.setMinimumSize(900, 600)
        self.worker: Optional[ScannerWorker] = None

        self.settings = QSettings('QuickScan', 'QuickScan')
        self.mode = self.settings.value('theme/mode', 'System')
        if self.mode not in theme.MODES:
            self.mode = 'System'
        self.palette_ = theme.resolve(self.mode)
        # Kept so the account pill can be repainted when the theme changes;
        # its colours are semantic, not fixed.
        self._account: Optional[tuple] = None
        self._history_loaded = False

        # ---- header --------------------------------------------------
        # The wordmark is split so the accent lands off-centre rather than on
        # the whole name; with the thick amber rule down the header's left
        # edge it gives the layout something asymmetric to sit against.
        title = QLabel('QUICK')
        title.setObjectName('AppTitle')
        mark = QLabel('//SCAN')
        mark.setObjectName('AppMark')

        wordmark = QHBoxLayout()
        wordmark.setSpacing(0)
        wordmark.addWidget(title)
        wordmark.addWidget(mark)
        wordmark.addStretch()

        subtitle = QLabel('MARKET SCANNER  ·  METATRADER 5')
        subtitle.setObjectName('AppSubtitle')

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title_block.addLayout(wordmark)
        title_block.addWidget(subtitle)

        self.account_label = QLabel('Not connected')
        self.account_label.setObjectName('Pill')

        self.theme_input = QComboBox()
        self.theme_input.addItems(theme.MODES)
        self.theme_input.setCurrentText(self.mode)
        self.theme_input.setToolTip('System follows your Windows light/dark setting.')
        self.theme_input.currentTextChanged.connect(self._change_theme)

        header = QFrame()
        header.setObjectName('HeaderBar')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 14, 12)
        header_layout.setSpacing(12)
        header_layout.addLayout(title_block)
        header_layout.addStretch()
        header_layout.addWidget(self.account_label)
        header_layout.addWidget(self.theme_input)

        # ---- symbols -------------------------------------------------
        self.symbol_filter = QLineEdit()
        self.symbol_filter.setPlaceholderText('Type to filter, e.g. Volatility')
        self.symbol_filter.textChanged.connect(self._filter_symbols)

        self.symbol_list = QListWidget()
        self.symbol_list.setSelectionMode(QListWidget.NoSelection)

        self.refresh_button = QPushButton('Load symbols from MetaTrader')
        self.refresh_button.clicked.connect(self._load_symbols)

        symbols_box = QFrame()
        symbols_box.setObjectName('Panel')
        symbols_layout = QVBoxLayout(symbols_box)
        symbols_layout.setContentsMargins(14, 12, 14, 14)
        symbols_layout.setSpacing(9)
        symbols_layout.addWidget(_section('Choose what to scan'))
        symbols_layout.addWidget(self.refresh_button)
        symbols_layout.addWidget(self.symbol_filter)
        symbols_layout.addWidget(self.symbol_list)

        # ---- settings ------------------------------------------------
        self.risk_input = QDoubleSpinBox()
        self.risk_input.setRange(0.1, 100.0)
        self.risk_input.setValue(1.0)
        self.risk_input.setSuffix(' %')
        self.risk_input.setToolTip('How much of the account a trade would risk.\n'
                                   'Only affects the position size the report suggests.')

        self.stop_input = QDoubleSpinBox()
        self.stop_input.setRange(0.5, 10.0)
        self.stop_input.setSingleStep(0.5)
        self.stop_input.setValue(2.0)
        self.stop_input.setToolTip('How far the stop-loss sits, in average candle sizes.\n'
                                   'Larger means more room and a smaller position.')

        self.timeframe_input = QComboBox()
        for label, token in TIMEFRAMES:
            self.timeframe_input.addItem(label, token)
        self.timeframe_input.setCurrentIndex(1)      # 5 minutes

        self.repeat_input = QCheckBox('Keep scanning as each candle closes')
        self.repeat_input.setChecked(True)

        settings_box = QFrame()
        settings_box.setObjectName('Panel')
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(14, 12, 14, 14)
        settings_layout.setSpacing(9)
        settings_layout.addWidget(_section('Settings'))
        for text, widget in (('Risk per trade', self.risk_input),
                             ('Stop distance (ATR)', self.stop_input),
                             ('Candle size', self.timeframe_input)):
            row = QHBoxLayout()
            label = QLabel(text)
            label.setObjectName('FieldLabel')
            label.setMinimumWidth(140)
            row.addWidget(label)
            row.addWidget(widget, 1)
            settings_layout.addLayout(row)
        settings_layout.addWidget(self.repeat_input)

        # ---- controls ------------------------------------------------
        self.start_button = QPushButton('Start scanning')
        self.start_button.setObjectName('Primary')
        self.start_button.setMinimumHeight(44)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self._start)
        self.stop_button = QPushButton('Stop')
        self.stop_button.setObjectName('Danger')
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setEnabled(False)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.clicked.connect(self._stop)

        controls = QHBoxLayout()
        controls.setSpacing(9)
        controls.addWidget(self.start_button, 2)
        controls.addWidget(self.stop_button, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(symbols_box, 1)
        left_layout.addWidget(settings_box)
        left_layout.addLayout(controls)

        # ---- output --------------------------------------------------
        self.output = QPlainTextEdit()
        self.output.setObjectName('Report')
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(20000)      # keep memory bounded
        # The reports are column-aligned tables. Wrapping a long line pushes
        # its tail to column zero and the columns stop lining up, so scroll
        # sideways instead, exactly as a terminal would.
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.highlighter = ReportHighlighter(self.output.document(), self.palette_)
        self.output.setPlainText(
            'Welcome to QuickScan.\n\n'
            'Before starting: open MetaTrader 5 and log in.\n\n'
            '  1. Press "Load symbols from MetaTrader"\n'
            '  2. Tick the symbols you want to watch\n'
            '  3. Press "Start scanning"\n\n'
            'Reports will appear here. Nothing is traded from this window.\n'
            '\n'
            'To see the levels drawn on your MT5 charts as well:\n'
            '  In MetaTrader, open Navigator (Ctrl+N), find QuickScanLauncher\n'
            '  under Expert Advisors, and drag it onto any one chart. Tick\n'
            '  "Allow Algo Trading", and make sure the Algo Trading button in\n'
            '  the toolbar is green.\n'
            '  It then opens a chart for each symbol you scan and adds the\n'
            '  drawing to it. This window works without it, but the charts\n'
            '  stay blank until it is running.\n')

        clear_button = QPushButton('Clear')
        clear_button.setObjectName('Ghost')
        clear_button.setCursor(Qt.PointingHandCursor)
        clear_button.clicked.connect(self.output.clear)

        reports_label = _section('Scan reports')

        right = QFrame()
        right.setObjectName('Panel')
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 12, 14, 14)
        right_layout.setSpacing(9)
        report_header = QHBoxLayout()
        report_header.addWidget(reports_label)
        report_header.addStretch()
        report_header.addWidget(clear_button)
        right_layout.addLayout(report_header)
        right_layout.addWidget(self.output)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 760])
        splitter.setChildrenCollapsible(False)

        # ---- tabs ----------------------------------------------------
        self.trades_tab = TradesTab(self.palette_)
        self.trades_tab.refresh_requested.connect(self._load_history)
        self.trades_tab.checklist.logged.connect(self.statusBar().showMessage)

        self.tabs = QTabWidget()
        self.tabs.addTab(splitter, 'Scan')
        self.tabs.addTab(self.trades_tab, 'Trades')
        self.tabs.currentChanged.connect(self._tab_changed)

        self.backdrop = TextureBackdrop(self.palette_)
        layout = QVBoxLayout(self.backdrop)
        layout.setContentsMargins(16, 16, 16, 10)
        layout.setSpacing(14)
        layout.addWidget(header)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(self.backdrop)

        self._apply_theme()
        self.statusBar().showMessage('Ready')
        self._watch_system_theme()
        self._load_symbols()

    # ---- theme -------------------------------------------------------
    def _watch_system_theme(self):
        """Repaint when Windows switches between light and dark."""
        try:
            hints = QApplication.instance().styleHints()
            hints.colorSchemeChanged.connect(lambda _: self._system_theme_changed())
        except AttributeError:
            pass       # Qt too old to report the change; the selector still works.

    def _system_theme_changed(self):
        if self.mode == 'System':
            self._apply_theme()

    def _change_theme(self, mode: str):
        self.mode = mode
        self.settings.setValue('theme/mode', mode)
        self._apply_theme()

    def _apply_theme(self):
        self.palette_ = theme.resolve(self.mode)
        app = QApplication.instance()
        # Fusion honours the palette for the bits a stylesheet cannot reach --
        # dropdown and spin arrows, the caret, focus rings.
        app.setPalette(theme.qpalette(self.palette_))
        app.setStyleSheet(theme.stylesheet(self.palette_, theme.mono_family()))
        self.backdrop.set_palette(self.palette_)
        self.highlighter.set_palette(self.palette_)
        self.trades_tab.set_palette(self.palette_)
        self._paint_account_pill()

    # ---- trade history -----------------------------------------------
    def _tab_changed(self, index: int):
        # Load the first time the tab is opened, not on every visit: it is a
        # round trip to the terminal and the history rarely changes mid-look.
        if self.tabs.tabText(index) == 'Trades' and not self._history_loaded:
            self._history_loaded = True
            self._load_history(self.trades_tab.period.currentData())

    def _load_history(self, days: int):
        self.trades_tab.set_busy(True)
        if self.worker is not None:
            # A scan owns the connection; ask it to do the read.
            self.worker.request_history(days)
            return
        self.history_loader = HistoryLoader(days)
        self.history_loader.loaded.connect(self._history_loaded_from_thread)
        self.history_loader.start()

    def _history_loaded_from_thread(self, rows: list, error: str):
        if error:
            self.statusBar().showMessage(error)
        self._show_history(rows)

    def _show_history(self, rows: list):
        self.trades_tab.set_busy(False)
        self.trades_tab.show_trades(rows)
        if rows:
            self.statusBar().showMessage(f'{len(rows)} closed trades')
        else:
            self.statusBar().showMessage('No closed trades in that period')

    # ---- symbols -----------------------------------------------------
    def _load_symbols(self):
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage('Loading symbols from MetaTrader...')
        self.loader = SymbolLoader()
        self.loader.loaded.connect(self._symbols_loaded)
        self.loader.start()

    def _symbols_loaded(self, names: list, error: str):
        self.refresh_button.setEnabled(True)
        if error:
            self.statusBar().showMessage(error)
            self.output.appendPlainText(f'\n{error}\n')
            return
        remembered = set(self._checked_symbols())
        self.symbol_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in remembered else Qt.Unchecked)
            self.symbol_list.addItem(item)
        self._filter_symbols(self.symbol_filter.text())
        self.statusBar().showMessage(f'{len(names)} symbols available')

    def _filter_symbols(self, text: str):
        needle = text.strip().lower()
        for i in range(self.symbol_list.count()):
            item = self.symbol_list.item(i)
            # A ticked symbol stays visible even when filtered out, so it is
            # never scanned invisibly or lost by typing in the filter box.
            hide = bool(needle) and needle not in item.text().lower() \
                and item.checkState() != Qt.Checked
            item.setHidden(hide)

    def _checked_symbols(self) -> List[str]:
        return [self.symbol_list.item(i).text()
                for i in range(self.symbol_list.count())
                if self.symbol_list.item(i).checkState() == Qt.Checked]

    # ---- run ---------------------------------------------------------
    def _start(self):
        symbols = self._checked_symbols()
        if not symbols:
            self.statusBar().showMessage('Tick at least one symbol first')
            self.output.appendPlainText('\nNothing to scan: no symbols are ticked.\n')
            return

        self.output.appendPlainText(f'\n{"=" * 70}\nStarting scan of {len(symbols)} symbol(s)\n{"=" * 70}\n')
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.worker = ScannerWorker(
            symbols, self.risk_input.value(), self.stop_input.value(),
            self.timeframe_input.currentData())
        self.worker.output.connect(self._append)
        self.worker.account.connect(self._show_account)
        self.worker.state.connect(self.statusBar().showMessage)
        self.worker.history.connect(self._show_history)
        self.worker.finished_cleanly.connect(self._scan_finished)
        # Without repeat the worker still runs one pass, then is asked to stop.
        if not self.repeat_input.isChecked():
            self.worker.output.connect(lambda _: self.worker and self.worker.stop())
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.statusBar().showMessage('Stopping...')
            self.worker.stop()
        self.stop_button.setEnabled(False)

    def _scan_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.worker = None

        # Offer to clear rather than clearing outright: the last report is
        # often the reason the scan was stopped, and silently discarding it
        # would be the wrong default.
        answer = QMessageBox.question(
            self, 'Scan stopped',
            'The scan has stopped.\n\nClear the reports from the screen?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.output.clear()
            self.statusBar().showMessage('Stopped, screen cleared')
        else:
            self.statusBar().showMessage('Stopped')

    def _append(self, text: str):
        if not text:
            return
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(QTextCursor.End)

    def _show_account(self, login: str, server: str, equity: float, is_demo: bool):
        self._account = (login, server, equity, is_demo)
        self._paint_account_pill()

    def _paint_account_pill(self):
        # A live account is called out loudly. Trading the wrong one by
        # accident is the expensive mistake this window can help prevent.
        p = self.palette_
        if self._account is None:
            self.account_label.setText('Not connected')
            self.account_label.setStyleSheet(
                f'color: {p.text_dim}; background: {p.field};'
                f' border: 1px solid {p.border};')
            return

        login, server, equity, is_demo = self._account
        colour = p.buy if is_demo else p.sell
        self.account_label.setText(
            f'{"DEMO" if is_demo else "LIVE"}  ·  {login}  ·  {server}'
            f'  ·  {equity:,.2f}')
        self.account_label.setStyleSheet(
            f'color: {colour}; background: {p.field};'
            f' border: 1px solid {colour};')

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('QuickScan')
    app.setOrganizationName('QuickScan')
    # Fusion is the one style that looks the same on every Windows version and
    # takes a custom palette properly; the native style ignores much of it.
    app.setStyle('Fusion')
    # Before the window exists: the stylesheet names these families, and Qt
    # resolves a font name once at the point it is applied.
    theme.load_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
