"""Record every distinct signal and later score it against what price did.

The engine emits confident grades (A+, 93/100) but nothing measures whether
an A+ actually beats a B. This logs each signal to an append-only JSONL file,
then resolves it from MT5 history to find which level price reached first.

Deliberate choices that keep the statistics honest:

* Entry is the signal-time market price, not the midpoint of the ideal zone.
  A zone midpoint assumes a limit fill that may never happen, which would
  flatter results by only counting setups price came back to.
* A repeated signal is not re-logged. A setup often persists for many
  candles; counting each candle would multiply one outcome into ten and
  bias the sample toward whichever setups linger longest.
* If a bar's range covers both the stop and a target, it is scored as a
  stop. OHLC cannot say which came first within a bar, so the pessimistic
  reading is the only one that cannot overstate performance.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOG_FILENAME = 'signals.jsonl'

OUTCOME_OPEN = 'OPEN'
OUTCOME_STOP = 'SL'
OUTCOME_EXPIRED = 'EXPIRED'


def _log_path(directory: Optional[str] = None) -> str:
    base = directory or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, LOG_FILENAME)


def load_signals(directory: Optional[str] = None) -> List[Dict[str, Any]]:
    path = _log_path(directory)
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
            except ValueError:
                continue  # skip a torn final line rather than lose the file
    return rows


def _rewrite(rows: List[Dict[str, Any]], directory: Optional[str] = None) -> None:
    path = _log_path(directory)
    temp = path + '.tmp'
    with open(temp, 'w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False) + '\n')
    os.replace(temp, path)


# How long an unresolved signal keeps blocking new ones for that symbol and
# direction. Matches the default resolution window (288 M5 bars = 1 day), so
# a signal that never reaches anything cannot block logging forever if
# outcomes.py is not run for a while.
SIGNAL_TTL_SECONDS = 86400


def _has_live_signal(rows: List[Dict[str, Any]], symbol: str, direction: str,
                     now_time: int) -> bool:
    """True while an unresolved signal for this symbol and direction stands.

    Dedupe cannot key on price: entry is the live bid and drifts every
    candle, so a setup that persists for hours would mint a fresh identity
    each scan and be counted many times over. One open trade per symbol and
    direction matches how the signal would actually be taken.
    """
    for row in rows:
        if (row.get('symbol') == symbol
                and row.get('direction') == direction
                and row.get('outcome') == OUTCOME_OPEN):
            age = now_time - int(row.get('signal_time', 0) or 0)
            if age < SIGNAL_TTL_SECONDS:
                return True
    return False


def log_signal(scan: Any, timeframe: str, signal_time: int,
               directory: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Append a signal if it is actionable and not a repeat. Never raises."""
    try:
        decision = str(scan.decision_panel.decision)
        if decision not in ('BUY NOW', 'SELL NOW'):
            return None

        entry = float(scan.bid)
        stop = float(getattr(scan.risk_panel.dynamic_stop, 'price', 0) or 0)
        if stop <= 0:
            return None

        targets = {}
        for target in scan.risk_panel.profit_targets[:3]:
            name = str(getattr(target, 'name', '')).upper()
            price = getattr(target, 'price', None)
            if name.startswith('TP') and price:
                targets[name] = float(price)
        if not targets:
            return None

        direction = 'BUY' if decision == 'BUY NOW' else 'SELL'
        rows = load_signals(directory)
        if _has_live_signal(rows, scan.symbol, direction, int(signal_time)):
            return None  # already in this trade; do not count it twice

        record = {
            'symbol': scan.symbol,
            'timeframe': timeframe,
            'logged_at_utc': datetime.now(timezone.utc).isoformat(),
            'signal_time': int(signal_time),
            'direction': direction,
            'decision': decision,
            'grade': str(scan.decision_panel.grade),
            'score': int(scan.decision_panel.entry_quality_score),
            'entry': entry,
            'stop': stop,
            'targets': targets,
            'outcome': OUTCOME_OPEN,
            'outcome_bars': None,
            'resolved_at_utc': None,
        }
        path = _log_path(directory)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, allow_nan=False) + '\n')
        return record
    except Exception:
        return None


def _classify_bar(row: Dict[str, Any], high: float, low: float) -> Optional[str]:
    """Which level this bar reached first, or None if it reached nothing.

    A bar covering both the stop and a target is reported as a stop; see the
    module docstring for why that direction of error is the safe one.
    """
    direction = row['direction']
    stop = float(row['stop'])
    targets = row.get('targets', {})

    if direction == 'BUY':
        hit_stop = low <= stop
        reached = [name for name, price in targets.items() if high >= float(price)]
        best = max(reached, key=lambda n: float(targets[n])) if reached else None
    else:
        hit_stop = high >= stop
        reached = [name for name, price in targets.items() if low <= float(price)]
        best = min(reached, key=lambda n: float(targets[n])) if reached else None

    if hit_stop:
        return OUTCOME_STOP
    return best


def resolve_pending(mt5: Any, timeframe_const: Any, max_bars: int = 288,
                    directory: Optional[str] = None) -> Dict[str, int]:
    """Score open signals against subsequent bars. Returns a counts summary."""
    rows = load_signals(directory)
    counts: Dict[str, int] = {}
    changed = False

    for row in rows:
        if row.get('outcome') != OUTCOME_OPEN:
            continue
        symbol = row['symbol']
        if not mt5.symbol_select(symbol, True):
            continue
        bars = mt5.copy_rates_from(symbol, timeframe_const,
                                   datetime.fromtimestamp(int(row['signal_time'])), max_bars)
        if bars is None or len(bars) == 0:
            continue

        outcome = None
        bars_taken = 0
        for index, bar in enumerate(bars):
            if int(bar['time']) <= int(row['signal_time']):
                continue  # only bars strictly after the signal count
            bars_taken = index
            outcome = _classify_bar(row, float(bar['high']), float(bar['low']))
            if outcome:
                break

        if outcome:
            row['outcome'] = outcome
            row['outcome_bars'] = bars_taken
            row['resolved_at_utc'] = datetime.now(timezone.utc).isoformat()
            counts[outcome] = counts.get(outcome, 0) + 1
            changed = True
        elif len(bars) >= max_bars:
            row['outcome'] = OUTCOME_EXPIRED
            row['resolved_at_utc'] = datetime.now(timezone.utc).isoformat()
            counts[OUTCOME_EXPIRED] = counts.get(OUTCOME_EXPIRED, 0) + 1
            changed = True

    if changed:
        _rewrite(rows, directory)
    return counts


def report(directory: Optional[str] = None) -> str:
    """Hit rates and expectancy grouped by grade."""
    rows = load_signals(directory)
    resolved = [r for r in rows if r.get('outcome') not in (None, OUTCOME_OPEN)]
    if not resolved:
        return (f'{len(rows)} signal(s) logged, none resolved yet.\n'
                'Resolution needs bars after the signal -- try again later.')

    by_grade: Dict[str, List[Dict[str, Any]]] = {}
    for row in resolved:
        by_grade.setdefault(str(row.get('grade', '?')), []).append(row)

    lines = [f'{len(rows)} signal(s) logged, {len(resolved)} resolved',
             '',
             f'{"Grade":<16}{"N":>4}{"TP1+":>7}{"SL":>7}{"Exp":>7}{"AvgR":>8}',
             '-' * 49]

    for grade in sorted(by_grade, key=lambda g: -len(by_grade[g])):
        group = by_grade[grade]
        wins = [r for r in group if str(r['outcome']).startswith('TP')]
        stops = [r for r in group if r['outcome'] == OUTCOME_STOP]
        expired = [r for r in group if r['outcome'] == OUTCOME_EXPIRED]

        total_r = 0.0
        for row in group:
            risk = abs(float(row['entry']) - float(row['stop']))
            if risk <= 0:
                continue
            if str(row['outcome']).startswith('TP'):
                hit = float(row['targets'][row['outcome']])
                total_r += abs(hit - float(row['entry'])) / risk
            elif row['outcome'] == OUTCOME_STOP:
                total_r -= 1.0
        avg_r = total_r / len(group) if group else 0.0

        lines.append(f'{grade:<16}{len(group):>4}{len(wins) / len(group):>6.0%}'
                     f'{len(stops) / len(group):>7.0%}{len(expired):>7}{avg_r:>8.2f}')

    lines += ['', 'TP1+ = reached at least one target before the stop.',
              'AvgR = mean R multiple, counting a stop as -1R.',
              'A bar spanning both stop and target is scored as a stop.']
    return '\n'.join(lines)
