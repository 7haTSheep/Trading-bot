"""Closed-trade history and the discipline statistics computed from it.

The discipline app this grew out of imported an MT5 report file and parsed it.
Here the terminal is already connected, so the trades are read straight from
it: no export step, no stale file, and the numbers cannot disagree with the
account.

MetaTrader records deals, not trades. A position that was opened, partially
closed and then closed again is three deals sharing one position_id, so the
deals are grouped back into positions before anything is measured. Volume-
weighted prices keep partial fills honest.

Stop-loss does not appear on a deal, only on the order that opened the
position, which is what makes the R multiple recoverable at all.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

CHECKLIST_ITEMS = [
    ('bias', 'Higher-timeframe bias confirmed before entry'),
    ('risk', 'Position size fits fixed risk % (no oversizing)'),
    ('stop', 'Stop loss placed before entering'),
    ('rr', 'Trade offers minimum 1:1.5 reward-to-risk'),
    ('state', "Not trading out of frustration or to 'win back' a loss"),
]


def data_dir() -> str:
    """Somewhere durable to keep the checklist log.

    Deliberately not the application folder: rebuilding or reinstalling the
    executable replaces that, and a discipline record you lose on an update is
    worse than none, because you would not notice it had gone.
    """
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    path = os.path.join(base, 'QuickScan')
    os.makedirs(path, exist_ok=True)
    return path


@dataclass
class Trade:
    position: int
    symbol: str
    side: str                  # BUY or SELL
    volume: float
    opened: int                # epoch seconds
    closed: int
    entry: float
    exit: float
    stop: Optional[float]
    profit: float              # net, including commission and swap
    r_multiple: Optional[float] = None

    @property
    def opened_at(self) -> datetime:
        return datetime.fromtimestamp(self.opened)

    @property
    def closed_at(self) -> datetime:
        return datetime.fromtimestamp(self.closed)


def _weighted(deals, price_attr: str = 'price') -> float:
    volume = sum(d.volume for d in deals)
    if volume <= 0:
        return float(getattr(deals[0], price_attr))
    return sum(getattr(d, price_attr) * d.volume for d in deals) / volume


def load_trades(mt5, days: int = 30) -> List[Trade]:
    """Closed positions from the connected terminal, oldest first.

    Assumes mt5 is already initialised, and must be called from whichever
    thread owns that connection.
    """
    now = datetime.now()
    start = now - timedelta(days=days)
    deals = mt5.history_deals_get(start, now) or []
    orders = mt5.history_orders_get(start, now) or []

    # The opening order carries the stop; the deal does not.
    stops: Dict[int, float] = {}
    for order in orders:
        position = getattr(order, 'position_id', 0)
        stop = getattr(order, 'sl', 0.0)
        if position and stop:
            stops.setdefault(position, stop)

    grouped = defaultdict(list)
    for deal in deals:
        if getattr(deal, 'position_id', 0):
            grouped[deal.position_id].append(deal)

    trades: List[Trade] = []
    for position, group in grouped.items():
        group.sort(key=lambda d: d.time)
        opening = [d for d in group if d.entry == mt5.DEAL_ENTRY_IN]
        closing = [d for d in group if d.entry in (mt5.DEAL_ENTRY_OUT,
                                                   mt5.DEAL_ENTRY_OUT_BY)]
        if not opening or not closing:
            continue                    # still open, or not a position at all

        side = 'BUY' if opening[0].type == mt5.DEAL_TYPE_BUY else 'SELL'
        entry = _weighted(opening)
        exit_price = _weighted(closing)
        stop = stops.get(position)

        r_multiple = None
        if stop and stop != entry:
            risk = abs(entry - stop)
            if risk > 0:
                gain = (exit_price - entry) if side == 'BUY' else (entry - exit_price)
                r_multiple = round(gain / risk, 2)

        trades.append(Trade(
            position=position,
            symbol=opening[0].symbol,
            side=side,
            volume=sum(d.volume for d in opening),
            opened=int(opening[0].time),
            closed=int(closing[-1].time),
            entry=entry,
            exit=exit_price,
            stop=stop,
            # profit alone omits costs, and costs are most of the argument
            # about whether these setups are worth trading at all.
            profit=sum(d.profit + getattr(d, 'commission', 0.0)
                       + getattr(d, 'swap', 0.0) for d in group),
            r_multiple=r_multiple,
        ))

    trades.sort(key=lambda t: t.closed)
    return trades


@dataclass
class Stats:
    count: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    avg_r: Optional[float] = None
    net_profit: float = 0.0
    best: float = 0.0
    worst: float = 0.0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    equity_curve: List[float] = field(default_factory=list)


def compute_stats(trades: List[Trade]) -> Stats:
    if not trades:
        return Stats()

    wins = [t for t in trades if t.profit > 0]
    losses = [t for t in trades if t.profit < 0]
    win_rate = len(wins) / len(trades) * 100.0
    avg_win = sum(t.profit for t in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t.profit for t in losses) / len(losses)) if losses else 0.0

    rated = [t.r_multiple for t in trades if t.r_multiple is not None]

    equity, curve = 0.0, []
    for trade in trades:
        equity += trade.profit
        curve.append(round(equity, 2))

    best_win = best_loss = current = 0
    kind = None
    for trade in trades:
        this = 'win' if trade.profit > 0 else 'loss' if trade.profit < 0 else None
        current = current + 1 if this == kind else 1
        kind = this
        if this == 'win':
            best_win = max(best_win, current)
        elif this == 'loss':
            best_loss = max(best_loss, current)

    return Stats(
        count=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        # Per-trade expected value at the observed hit rate; the number that
        # says whether repeating this is worth doing.
        expectancy=(win_rate / 100.0) * avg_win - (1 - win_rate / 100.0) * avg_loss,
        avg_r=sum(rated) / len(rated) if rated else None,
        net_profit=sum(t.profit for t in trades),
        best=max(t.profit for t in trades),
        worst=min(t.profit for t in trades),
        max_win_streak=best_win,
        max_loss_streak=best_loss,
        equity_curve=curve,
    )


# ---- checklist log ---------------------------------------------------
CHECKLIST_LOG = 'discipline.jsonl'


def log_checklist(ticked: Dict[str, bool], note: str = '') -> None:
    record = {
        'time': datetime.now().isoformat(timespec='seconds'),
        'ticked': {key: bool(ticked.get(key)) for key, _ in CHECKLIST_ITEMS},
        'complete': all(ticked.get(key) for key, _ in CHECKLIST_ITEMS),
        'note': note,
    }
    path = os.path.join(data_dir(), CHECKLIST_LOG)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record) + '\n')


def load_checklist_log(limit: int = 200) -> List[Dict[str, Any]]:
    path = os.path.join(data_dir(), CHECKLIST_LOG)
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue          # a torn last line should not lose the rest
    return rows[-limit:]
