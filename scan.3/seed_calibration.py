"""Seeds the calibration log from historical price, not live signals.

Live signals arrive at roughly 0.74 per symbol per day, so the 200-trade
evidence bar is about 269 days away per symbol. Replaying history reaches
it in minutes.

What this replays is the core setup the scanner trades: a pullback into the
EMA20 zone with the EMA stack aligned, a stop 2 ATR away to match
--stop-atr 2.0, and targets at 1.5 / 2.5 / 4.0 ATR, each resolved against
the bars that followed. It is an approximation of the scanner's full
decision, which also weighs VWAP, opening ranges, RSI, ADX and volume, so
these records carry source='historical' and stay distinguishable from live
ones rather than being passed off as the same evidence.

    python seed_calibration.py               replay the default symbols
    python seed_calibration.py --bars 20000  use a longer history
    python seed_calibration.py --clear       drop previous historical rows
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np
import MetaTrader5 as mt5

import outcome_tracker

STOP_ATR = 2.0
TP_ATR = (1.5, 2.5, 4.0)
RESOLVE_BARS = 288          # same window outcomes.py allows a live signal


def ema(values: np.ndarray, span: int) -> np.ndarray:
    k = 2 / (span + 1)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def atr_series(high, low, close, n=14) -> np.ndarray:
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    out = np.full(len(high), np.nan)
    for i in range(n, len(tr) + 1):
        out[i] = tr[i - n:i].mean()
    return out


def resolve(high, low, start: int, is_buy: bool, stop: float,
            targets: Dict[str, float]) -> tuple:
    """First level price reached. A bar covering both scores as the stop."""
    limit = min(start + 1 + RESOLVE_BARS, len(high))
    for j in range(start + 1, limit):
        hit_stop = low[j] <= stop if is_buy else high[j] >= stop
        if hit_stop:
            return outcome_tracker.OUTCOME_STOP, j - start
        reached = [name for name, price in targets.items()
                   if (high[j] >= price if is_buy else low[j] <= price)]
        if reached:
            best = max(reached, key=lambda n: targets[n]) if is_buy \
                else min(reached, key=lambda n: targets[n])
            return best, j - start
    return outcome_tracker.OUTCOME_EXPIRED, limit - start - 1


def replay(symbol: str, bars: int) -> List[Dict[str, Any]]:
    if not mt5.symbol_select(symbol, True):
        return []
    data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    if data is None or len(data) < 500:
        return []
    # Entry crosses the spread, which is decisive here rather than a detail:
    # it costs 0.03-0.05R on these symbols, larger than most of the measured
    # edge. Ignoring it would have the calibration approve symbols that lose
    # money net. Current spread stands in for its history.
    info = mt5.symbol_info(symbol)
    spread = (info.spread * info.point) if info else 0.0
    close = data['close'].astype(float)
    high = data['high'].astype(float)
    low = data['low'].astype(float)
    times = data['time'].astype(np.int64)

    e20, e50, e200 = ema(close, 20), ema(close, 50), ema(close, 200)
    atr = atr_series(high, low, close)

    records: List[Dict[str, Any]] = []
    inside_previous = False
    for i in range(200, len(close) - RESOLVE_BARS - 1):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        # stack_label in quickscan requires a full ordering of the EMAs.
        bull = e20[i] > e50[i] > e200[i]
        bear = e20[i] < e50[i] < e200[i]
        if not (bull or bear):
            inside_previous = False
            continue

        zone_low, zone_high = e20[i] - 0.2 * a, e20[i] + 0.2 * a
        inside = low[i] <= zone_high and high[i] >= zone_low
        # Only the first bar of a touch is an entry; a run of bars inside the
        # zone is one setup, not one per candle.
        entering = inside and not inside_previous
        inside_previous = inside
        if not entering:
            continue

        # A buy fills at the ask and a sell at the bid, so the entry is worse
        # than the close by the spread while stop and targets stay put.
        mid = close[i]
        entry = mid + spread if bull else mid - spread
        stop = mid - STOP_ATR * a if bull else mid + STOP_ATR * a
        targets = {f'TP{n+1}': (mid + m * a if bull else mid - m * a)
                   for n, m in enumerate(TP_ATR)}
        outcome, took = resolve(high, low, i, bull, stop, targets)
        records.append({
            'source': 'historical',
            'symbol': symbol,
            'timeframe': 'M5',
            'logged_at_utc': datetime.now(timezone.utc).isoformat(),
            'signal_time': int(times[i]),
            'direction': 'BUY' if bull else 'SELL',
            'decision': 'BUY NOW' if bull else 'SELL NOW',
            'grade': 'historical',
            'score': 0,                     # the live score is not reproduced here
            'entry': float(entry),
            'stop': float(stop),
            'targets': {k: float(v) for k, v in targets.items()},
            'outcome': outcome,
            'outcome_bars': int(took),
            'resolved_at_utc': datetime.now(timezone.utc).isoformat(),
        })
    return records


def main():
    parser = argparse.ArgumentParser(description='Seed calibration from historical price')
    parser.add_argument('symbols', nargs='*', help='symbols (default: those already in the log)')
    parser.add_argument('--bars', type=int, default=20000, help='M5 bars of history per symbol')
    parser.add_argument('--clear', action='store_true', help='remove existing historical rows first')
    args = parser.parse_args()

    existing = outcome_tracker.load_signals()
    live = [r for r in existing if r.get('source') != 'historical']
    kept = live if args.clear else existing

    symbols = args.symbols or sorted({r['symbol'] for r in live}) or [
        'Volatility 10 (1s) Index', 'Volatility 15 Index', 'Volatility 25 Index',
        'Volatility 75 (1s) Index']

    if not mt5.initialize():
        print('MT5 init failed - is the terminal running?')
        return
    try:
        produced = []
        for symbol in symbols:
            rows = replay(symbol, args.bars)
            produced.extend(rows)
            wins = sum(1 for r in rows if str(r['outcome']).startswith('TP'))
            print(f'{symbol:28s} {len(rows):5d} setups   '
                  f'{100*wins/len(rows) if rows else 0:5.1f}% reached a target')
    finally:
        mt5.shutdown()

    outcome_tracker._rewrite(kept + produced)
    print()
    print(f'wrote {len(produced)} historical rows alongside {len(live)} live ones')
    print('run "python calibration.py" to see the effect')


if __name__ == '__main__':
    main()
