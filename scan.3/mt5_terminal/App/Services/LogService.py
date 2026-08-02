"""
LogService.py — Centralised rotating log management.

Creates separate loggers for: application, scanner, trading, ai, errors, performance.
All logs are written to Logs/ directory with daily rotation.
"""
from __future__ import annotations
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[3] / 'Logs'


class LogService:
    """Singleton log service providing named loggers for every application layer."""

    _instance: 'LogService | None' = None
    _loggers: dict[str, logging.Logger] = {}

    def __new__(cls) -> 'LogService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    def initialise(self, level: str = 'INFO') -> None:
        if self._initialised:
            return
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        for name in ('app', 'scanner', 'trading', 'ai', 'errors', 'performance'):
            logger = logging.getLogger(f'mt5_terminal.{name}')
            logger.setLevel(numeric_level)
            if not logger.handlers:
                fh = RotatingFileHandler(
                    LOGS_DIR / f'{name}.log',
                    maxBytes=5 * 1024 * 1024,
                    backupCount=5,
                    encoding='utf-8',
                )
                fh.setFormatter(logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
                logger.addHandler(fh)
                # Also pipe to console in dev mode
                ch = logging.StreamHandler()
                ch.setLevel(logging.WARNING)
                ch.setFormatter(logging.Formatter('%(levelname)s | %(name)s | %(message)s'))
                logger.addHandler(ch)
            self._loggers[name] = logger
        self._initialised = True

    def get(self, name: str) -> logging.Logger:
        return self._loggers.get(name, logging.getLogger('mt5_terminal.app'))


# Module-level convenience accessor
log_service = LogService()
