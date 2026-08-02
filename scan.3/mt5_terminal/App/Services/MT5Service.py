"""
MT5Service.py — Centralised MetaTrader 5 connection and data management.

All raw MT5 API calls live here. The rest of the application never imports
MetaTrader5 directly; they call this service instead.
"""
from __future__ import annotations

import sys
from typing import Optional
from pathlib import Path

import numpy as np

# Allow running without MT5 installed (demo mode / CI)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None  # type: ignore

from App.Services.LogService import log_service

_log = log_service.get('app')


class MT5ConnectionError(RuntimeError):
    pass


class MT5Service:
    """Singleton wrapper around the MetaTrader5 Python library."""

    _instance: 'MT5Service | None' = None

    def __new__(cls) -> 'MT5Service':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connected = False
        return cls._instance

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            _log.warning('MetaTrader5 library not available — running in DEMO mode.')
            return False
        if self._connected:
            return True
        if not mt5.initialize():
            _log.error('mt5.initialize() failed: %s', mt5.last_error())
            return False
        account = mt5.account_info()
        if account is None:
            _log.error('MT5 account_info() returned None.')
            mt5.shutdown()
            return False
        _log.info(
            'Connected to MT5 — account=%s, broker=%s, server=%s',
            account.login, account.company, account.server
        )
        self._connected = True
        return True

    def disconnect(self) -> None:
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    def get_account_info(self) -> dict:
        """Return account info as a plain dict."""
        if not MT5_AVAILABLE or not self._connected:
            return self._demo_account()
        info = mt5.account_info()
        if info is None:
            return {}
        return info._asdict()

    @staticmethod
    def _demo_account() -> dict:
        return {
            'login': 0,
            'balance': 10_000.00,
            'equity': 10_000.00,
            'margin': 0.0,
            'margin_free': 10_000.00,
            'margin_level': 0.0,
            'profit': 0.0,
            'currency': 'USD',
            'company': 'DEMO MODE',
            'server': 'localhost',
            'name': 'Demo Account',
        }

    # ------------------------------------------------------------------
    # Symbols
    # ------------------------------------------------------------------
    def get_symbols(self) -> list[str]:
        """Return all available symbol names."""
        if not MT5_AVAILABLE or not self._connected:
            return []
        symbols = mt5.symbols_get()
        return [s.name for s in symbols] if symbols else []

    def symbol_info(self, symbol: str) -> Optional[dict]:
        if not MT5_AVAILABLE or not self._connected:
            return None
        info = mt5.symbol_info(symbol)
        return info._asdict() if info else None

    def symbol_info_tick(self, symbol: str) -> Optional[dict]:
        if not MT5_AVAILABLE or not self._connected:
            return None
        tick = mt5.symbol_info_tick(symbol)
        return tick._asdict() if tick else None

    # ------------------------------------------------------------------
    # OHLCV Bars
    # ------------------------------------------------------------------
    def get_rates(
        self, symbol: str, timeframe_str: str, count: int = 500
    ) -> Optional[np.ndarray]:
        """
        Fetch OHLCV bars. timeframe_str can be 'M1','M5','M15','H1','H4','D1'.
        Returns a structured numpy array with fields:
            time, open, high, low, close, tick_volume, spread, real_volume
        """
        if not MT5_AVAILABLE or not self._connected:
            return None
        tf_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
        }
        tf = tf_map.get(timeframe_str.upper())
        if tf is None:
            _log.warning('Unknown timeframe: %s', timeframe_str)
            return None
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            _log.warning('No rates returned for %s %s', symbol, timeframe_str)
        return rates
