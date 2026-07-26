"""
DatabaseService.py — SQLite persistence for scan history, decisions, and alerts.

Designed so every scan result is stored for future backtesting, win-rate analytics,
and trade journal generation.
"""
from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from App.Services.LogService import log_service


class DatabaseService:
    """Thread-safe SQLite service wrapping all persistence operations."""

    def __init__(self, db_path: str = 'Logs/history.db') -> None:
        self._db_path = Path(__file__).resolve().parents[3] / db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = log_service.get('app')
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        with self._connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS scan_results (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    bid         REAL,
                    spread      REAL,
                    decision    TEXT,
                    grade       TEXT,
                    quality     INTEGER,
                    confidence  TEXT,
                    bias        TEXT,
                    stop        REAL,
                    tp1         REAL,
                    tp2         REAL,
                    tp3         REAL,
                    rr          REAL,
                    full_json   TEXT
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    alert_type  TEXT,
                    message     TEXT,
                    acknowledged INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS settings_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ------------------------------------------------------------------
    # Scan Results
    # ------------------------------------------------------------------
    def insert_scan(self, result_dict: dict[str, Any]) -> None:
        """Persist a ScanResult.to_dict() payload."""
        try:
            dp = result_dict.get('decision_panel', {})
            rp = result_dict.get('risk_panel', {})
            sm = result_dict.get('summary', {})
            targets = rp.get('profit_targets', [])
            ts = datetime.utcnow().isoformat()
            with self._connect() as con:
                con.execute(
                    """
                    INSERT INTO scan_results
                        (timestamp, symbol, bid, spread, decision, grade, quality,
                         confidence, bias, stop, tp1, tp2, tp3, rr, full_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ts,
                        result_dict.get('symbol', ''),
                        result_dict.get('bid'),
                        result_dict.get('spread'),
                        dp.get('decision'),
                        dp.get('grade'),
                        dp.get('entry_quality_score'),
                        dp.get('confidence'),
                        sm.get('bias'),
                        sm.get('stop'),
                        targets[0]['price'] if len(targets) > 0 else None,
                        targets[1]['price'] if len(targets) > 1 else None,
                        targets[2]['price'] if len(targets) > 2 else None,
                        targets[0]['rr'] if len(targets) > 0 else None,
                        json.dumps(result_dict),
                    )
                )
        except Exception as exc:
            self._log.error('DatabaseService.insert_scan failed: %s', exc)

    def get_recent_scans(
        self, symbol: Optional[str] = None, limit: int = 200
    ) -> list[dict]:
        """Return recent scan rows as dicts, optionally filtered by symbol."""
        query = 'SELECT * FROM scan_results'
        params: tuple = ()
        if symbol:
            query += ' WHERE symbol = ?'
            params = (symbol,)
        query += f' ORDER BY id DESC LIMIT {limit}'
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    def insert_alert(self, symbol: str, alert_type: str, message: str) -> None:
        ts = datetime.utcnow().isoformat()
        with self._connect() as con:
            con.execute(
                'INSERT INTO alerts (timestamp, symbol, alert_type, message) VALUES (?,?,?,?)',
                (ts, symbol, alert_type, message)
            )

    def get_unacknowledged_alerts(self) -> list[dict]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                'SELECT * FROM alerts WHERE acknowledged=0 ORDER BY id DESC'
            ).fetchall()
        return [dict(r) for r in rows]
