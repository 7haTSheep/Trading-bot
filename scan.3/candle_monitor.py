"""Candle-close event detection for the MT5 scanner.

The monitor polls MT5 for the current bar's identity (its open timestamp).
When that identity changes, the previous bar has closed -- that transition is
the analysis trigger. The on-screen countdown is display only and never
decides when analysis runs, so the scanner can't drift out of sync with real
candle boundaries the way a fixed sleep timer does.
"""
from datetime import datetime
from typing import Any, Dict, Optional


TIMEFRAME_SPECS = {
    '1m': ('M1', 'TIMEFRAME_M1', 60),
    '5m': ('M5', 'TIMEFRAME_M5', 300),
    '15m': ('M15', 'TIMEFRAME_M15', 900),
    '30m': ('M30', 'TIMEFRAME_M30', 1800),
    '1h': ('H1', 'TIMEFRAME_H1', 3600),
    '4h': ('H4', 'TIMEFRAME_H4', 14400),
    'daily': ('D1', 'TIMEFRAME_D1', 86400),
    '1d': ('D1', 'TIMEFRAME_D1', 86400),
}


def is_timeframe_token(token: str) -> bool:
    return token.strip().lower() in TIMEFRAME_SPECS


def timeframe_spec(token: str, mt5: Any) -> Dict[str, Any]:
    """Resolve a command-line timeframe token to an MT5 timeframe constant."""
    normalized = token.strip().lower()
    if normalized not in TIMEFRAME_SPECS:
        supported = ', '.join(TIMEFRAME_SPECS)
        raise ValueError(f'Unsupported candle timeframe "{token}". Use: {supported}.')
    label, attribute, seconds = TIMEFRAME_SPECS[normalized]
    return {'token': normalized, 'label': label,
            'mt5_timeframe': getattr(mt5, attribute), 'seconds': seconds}


class CandleMonitor:
    """Tracks MT5 candle timestamps and prevents duplicate candle processing."""

    def __init__(self, mt5: Any, symbol: str, spec: Dict[str, Any]):
        self.mt5 = mt5
        self.symbol = symbol
        self.spec = spec
        self.current_candle_time: Optional[int] = None
        self.last_processed_candle: Optional[int] = None

    def latest_candle(self) -> Optional[Any]:
        rates = self.mt5.copy_rates_from_pos(self.symbol, self.spec['mt5_timeframe'], 0, 1)
        if rates is None or len(rates) == 0:
            return None
        return rates[-1]

    @staticmethod
    def candle_time(candle: Any) -> Optional[int]:
        try:
            return int(candle['time'])
        except (KeyError, TypeError, ValueError, IndexError):
            return None

    def initialize(self) -> Optional[Any]:
        """Record the currently-open candle without treating it as an event."""
        candle = self.latest_candle()
        self.current_candle_time = self.candle_time(candle) if candle is not None else None
        return candle

    def new_closed_candle(self) -> Optional[int]:
        """Return the just-closed candle's open time once, else None.

        Returns each closed candle at most once, so a slow analysis pass can
        never cause the same bar to be scanned twice.
        """
        candle = self.latest_candle()
        candle_id = self.candle_time(candle) if candle is not None else None
        if candle_id is None:
            return None
        if self.current_candle_time is None:
            self.current_candle_time = candle_id
            return None
        if candle_id == self.current_candle_time:
            return None
        closed_candle = self.current_candle_time
        self.current_candle_time = candle_id
        if closed_candle == self.last_processed_candle:
            return None
        self.last_processed_candle = closed_candle
        return closed_candle

    def seconds_remaining(self) -> Optional[int]:
        """Seconds until the current candle closes, for display only."""
        if self.current_candle_time is None:
            return None
        end = self.current_candle_time + self.spec['seconds']
        return max(0, end - int(datetime.now().timestamp()))

    @staticmethod
    def format_candle_time(candle_id: Optional[int]) -> str:
        if candle_id is None:
            return '--:--:--'
        return datetime.fromtimestamp(candle_id).strftime('%H:%M:%S')

    @staticmethod
    def format_countdown(seconds: Optional[int]) -> str:
        if seconds is None:
            return '--:--'
        return f'{seconds // 60:02d}:{seconds % 60:02d}'
