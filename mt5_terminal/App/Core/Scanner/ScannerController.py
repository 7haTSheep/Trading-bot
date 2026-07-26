"""
ScannerController.py — Background scanning engine using PySide6 QThread.

Responsibilities:
- Connect to MT5 via MT5Service
- Run scan_symbol() from the existing trading engine (quickscan.py)
- Emit results as Qt signals to the main thread — never block the UI
- Support pause/resume/stop/change-interval operations

The trading engine is imported as an adapter; zero trading logic lives here.
"""
from __future__ import annotations

import time
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot, QMutex, QMutexLocker

from App.Services.LogService import log_service
from App.Services.MT5Service import MT5Service

# -----------------------------------------------------------------------
# Import trading engine — it lives one directory level above mt5_terminal
# -----------------------------------------------------------------------
_ENGINE_PATH = Path(__file__).resolve().parents[4]
if str(_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(_ENGINE_PATH))

try:
    from quickscan import scan_symbol          # type: ignore
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False
    scan_symbol = None  # type: ignore

_log = log_service.get('scanner')


class _ScanWorker(QObject):
    """
    Runs inside a dedicated QThread.
    Calls scan_symbol() for each symbol in the watchlist and emits results.
    """

    # Emitted for each completed symbol scan
    result_ready = Signal(dict)          # serialised ScanResult dict
    error_occurred = Signal(str, str)    # (symbol, error message)
    scan_cycle_done = Signal()           # fired after a full sweep
    status_changed = Signal(str)         # status messages for the UI

    def __init__(
        self,
        symbols: list[str],
        interval: int = 30,
        risk_pct: float = 5.0,
    ) -> None:
        super().__init__()
        self._symbols = symbols
        self._interval = interval
        self._risk_pct = risk_pct
        self._running = False
        self._paused = False
        self._mutex = QMutex()

    # ------------------------------------------------------------------
    # Control interface (called from any thread)
    # ------------------------------------------------------------------
    def set_symbols(self, symbols: list[str]) -> None:
        with QMutexLocker(self._mutex):
            self._symbols = list(symbols)

    def set_interval(self, seconds: int) -> None:
        with QMutexLocker(self._mutex):
            self._interval = max(5, seconds)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Main loop (runs in QThread)
    # ------------------------------------------------------------------
    @Slot()
    def run(self) -> None:
        self._running = True
        self.status_changed.emit('Scanner started')
        _log.info('Scanner worker started with %d symbols', len(self._symbols))

        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue

            with QMutexLocker(self._mutex):
                symbols = list(self._symbols)
                interval = self._interval
                risk = self._risk_pct

            for sym in symbols:
                if not self._running:
                    break
                if self._paused:
                    break

                self.status_changed.emit(f'Scanning {sym}…')
                try:
                    result = self._scan_one(sym, risk)
                    if result:
                        self.result_ready.emit(result)
                        _log.debug('Scan OK: %s  decision=%s', sym, result.get('decision_panel', {}).get('decision'))
                except Exception as exc:
                    _log.exception('Scan error for %s: %s', sym, exc)
                    self.error_occurred.emit(sym, str(exc))

            self.scan_cycle_done.emit()
            self.status_changed.emit(f'Cycle complete — next in {interval}s')

            # Sleep in small chunks so we can exit promptly
            for _ in range(interval * 2):
                if not self._running:
                    break
                time.sleep(0.5)

        self.status_changed.emit('Scanner stopped')
        _log.info('Scanner worker stopped')

    # ------------------------------------------------------------------
    # Private: single symbol scan
    # ------------------------------------------------------------------
    def _scan_one(self, symbol: str, risk_pct: float) -> Optional[dict]:
        if not ENGINE_AVAILABLE:
            return self._demo_result(symbol)

        result = scan_symbol(symbol, risk_pct=risk_pct, stop_atr_mult=2.0, equity=None, compare_rows=[])
        if result is None:
            return None

        # Serialise to dict (ScanResult is a dataclass)
        return _serialise_scan_result(result)

    @staticmethod
    def _demo_result(symbol: str) -> dict:
        """Return a synthetic result when the engine is unavailable."""
        import random, time as _time
        decisions = ['ENTER LONG', 'ENTER SHORT', 'WAIT - Setup Forming', 'WAIT - Unfavourable']
        grades = ['A', 'B', 'C', 'D']
        d = random.choice(decisions)
        price = round(random.uniform(50, 2000), 3)
        stop = round(price * (1 - 0.015 * random.uniform(0.5, 2)), 3)
        tp1 = round(price * (1 + 0.02 * random.uniform(0.5, 2)), 3)
        tp2 = round(price * (1 + 0.04 * random.uniform(0.5, 2)), 3)
        tp3 = round(price * (1 + 0.07 * random.uniform(0.5, 2)), 3)
        return {
            'symbol': symbol,
            'bid': price,
            'ask': price + 0.5,
            'spread': 0.5,
            'timestamp': _time.strftime('%Y-%m-%d %H:%M:%S'),
            'decision_panel': {
                'decision': d,
                'grade': random.choice(grades),
                'entry_quality_score': random.randint(40, 95),
                'confidence': random.choice(['Low', 'Medium', 'High']),
                'waiting_for': [] if 'ENTER' in d else ['RSI confirmation', 'Break of structure'],
                'invalidation': 'Price closes below key support',
                'entry_zone': (price * 0.995, price * 1.005),
            },
            'risk_panel': {
                'stop_loss': stop,
                'profit_targets': [
                    {'label': 'TP1 (1:1)', 'price': tp1, 'rr': 1.0, 'hit_probability': 'High'},
                    {'label': 'TP2 (1:2)', 'price': tp2, 'rr': 2.0, 'hit_probability': 'Medium'},
                    {'label': 'TP3 (1:3)', 'price': tp3, 'rr': 3.0, 'hit_probability': 'Low'},
                ],
                'risk_amount': 500.0,
                'lot_size': 0.50,
            },
            'summary': {
                'bias': random.choice(['Bullish', 'Bearish', 'Neutral']),
                'stop': stop,
                'score': random.randint(50, 100),
            },
            'trend_panel': {
                'ema_alignment': random.choice(['Full Bullish Stack', 'Full Bearish Stack', 'Mixed']),
                'rsi': random.uniform(30, 70),
                'adx': random.uniform(15, 55),
                'atr': random.uniform(10, 100),
            },
            'chart_panel': {
                'markings': [
                    {'type': 'horizontal', 'price': stop, 'color': '#EF4444', 'label': 'Stop Loss'},
                    {'type': 'horizontal', 'price': tp1,  'color': '#22C55E', 'label': 'TP1'},
                    {'type': 'horizontal', 'price': tp2,  'color': '#22C55E', 'label': 'TP2'},
                    {'type': 'horizontal', 'price': tp3,  'color': '#22C55E', 'label': 'TP3'},
                ],
            },
            'checklist': {
                'items': [
                    {'name': 'EMA Alignment',      'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'RSI Zone',            'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'Market Structure',    'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'ORB Confirmation',    'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'VWAP Position',       'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'Session Active',      'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                    {'name': 'Spread Acceptable',   'status': random.choice(['PASS', 'FAIL', 'WARN'])},
                ],
            },
        }


def _serialise_scan_result(result) -> dict:
    """Convert a ScanResult dataclass to a JSON-serialisable dict."""
    # If the engine returns a dict already, pass through
    if isinstance(result, dict):
        return result

    # Attempt dataclass introspection
    import dataclasses
    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)

    # Fallback: use __dict__
    return vars(result)


class ScannerController(QObject):
    """
    Public interface for the scanner. Owns the QThread lifecycle.

    UI layer interacts with this object only.
    """

    # Forwarded worker signals
    result_ready = Signal(dict)
    error_occurred = Signal(str, str)
    scan_cycle_done = Signal()
    status_changed = Signal(str)
    scanner_state_changed = Signal(bool)  # True=running, False=stopped

    def __init__(
        self,
        symbols: list[str],
        interval: int = 30,
        risk_pct: float = 5.0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._worker: Optional[_ScanWorker] = None
        self._thread: Optional[QThread] = None
        self._symbols = symbols
        self._interval = interval
        self._risk_pct = risk_pct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._thread = QThread()
        self._worker = _ScanWorker(self._symbols, self._interval, self._risk_pct)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._thread.started.connect(self._worker.run)
        self._worker.result_ready.connect(self.result_ready)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.scan_cycle_done.connect(self.scan_cycle_done)
        self._worker.status_changed.connect(self.status_changed)

        self._thread.start()
        self.scanner_state_changed.emit(True)
        _log.info('ScannerController started')

    def stop(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None
        self.scanner_state_changed.emit(False)
        _log.info('ScannerController stopped')

    def pause(self) -> None:
        if self._worker:
            self._worker.pause()

    def resume(self) -> None:
        if self._worker:
            self._worker.resume()

    def set_symbols(self, symbols: list[str]) -> None:
        self._symbols = symbols
        if self._worker:
            self._worker.set_symbols(symbols)

    def set_interval(self, seconds: int) -> None:
        self._interval = seconds
        if self._worker:
            self._worker.set_interval(seconds)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.isRunning())
