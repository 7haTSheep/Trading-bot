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

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

TIMEFRAMES = [('1 minute', '1m'), ('5 minutes', '5m'), ('15 minutes', '15m'),
              ('30 minutes', '30m'), ('1 hour', '1h'), ('4 hours', '4h')]


class ScannerWorker(QThread):
    """Runs the scanner off the GUI thread and reports back by signal."""

    output = Signal(str)
    account = Signal(str, str, float, bool)   # login, server, equity, is_demo
    state = Signal(str)
    finished_cleanly = Signal()

    def __init__(self, symbols: List[str], risk: float, stop_atr: float, timeframe: str):
        super().__init__()
        self.symbols = symbols
        self.risk = risk
        self.stop_atr = stop_atr
        self.timeframe = timeframe
        self._stop = False

    def stop(self):
        self._stop = True

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

    def _scan_all(self, quickscan, equity, symbols: Optional[List[str]] = None):
        for symbol in (symbols if symbols is not None else self.symbols):
            if self._stop:
                return
            self.state.emit(f'Scanning {symbol}')
            # scan_symbol prints its report; capturing it keeps the window and
            # the command line showing exactly the same thing.
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    quickscan.scan_symbol(symbol, self.risk, self.stop_atr, equity)
            except Exception as exc:
                buffer.write(f'\n{symbol}: could not be scanned ({exc})\n')
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('QuickScan')
        self.resize(1150, 760)
        self.worker: Optional[ScannerWorker] = None

        self.account_label = QLabel('Not connected')
        self.account_label.setStyleSheet('font-weight: bold;')

        # ---- symbols -------------------------------------------------
        self.symbol_filter = QLineEdit()
        self.symbol_filter.setPlaceholderText('Type to filter, e.g. Volatility')
        self.symbol_filter.textChanged.connect(self._filter_symbols)

        self.symbol_list = QListWidget()
        self.symbol_list.setSelectionMode(QListWidget.NoSelection)

        self.refresh_button = QPushButton('Load symbols from MetaTrader')
        self.refresh_button.clicked.connect(self._load_symbols)

        symbols_box = QGroupBox('1. Choose what to scan')
        symbols_layout = QVBoxLayout(symbols_box)
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

        settings_box = QGroupBox('2. Settings')
        settings_layout = QVBoxLayout(settings_box)
        for text, widget in (('Risk per trade', self.risk_input),
                             ('Stop distance (ATR)', self.stop_input),
                             ('Candle size', self.timeframe_input)):
            row = QHBoxLayout()
            label = QLabel(text)
            label.setMinimumWidth(140)
            row.addWidget(label)
            row.addWidget(widget)
            settings_layout.addLayout(row)
        settings_layout.addWidget(self.repeat_input)

        # ---- controls ------------------------------------------------
        self.start_button = QPushButton('Start scanning')
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._start)
        self.stop_button = QPushButton('Stop')
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(symbols_box, 1)
        left_layout.addWidget(settings_box)
        left_layout.addLayout(controls)

        # ---- output --------------------------------------------------
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont('Consolas', 9))
        self.output.setMaximumBlockCount(20000)      # keep memory bounded
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
        clear_button.clicked.connect(self.output.clear)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        header = QHBoxLayout()
        header.addWidget(QLabel('Scan reports'))
        header.addStretch()
        header.addWidget(clear_button)
        right_layout.addLayout(header)
        right_layout.addWidget(self.output)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 770])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.account_label)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

        self.statusBar().showMessage('Ready')
        self._load_symbols()

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
        # A live account is called out loudly. Trading the wrong one by
        # accident is the expensive mistake this window can help prevent.
        kind = 'DEMO' if is_demo else 'LIVE'
        colour = '#1a7f37' if is_demo else '#b3261e'
        self.account_label.setText(
            f'Account {login} · {server} · {kind} · equity {equity:,.2f}')
        self.account_label.setStyleSheet(
            f'font-weight: bold; color: white; background: {colour}; padding: 6px;')

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('QuickScan')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
