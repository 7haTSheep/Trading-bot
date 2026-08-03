"""Does waiting for price to reclaim the zone beat entering on first touch?

Replays both entry rules through the scanner's actual stop and target
geometry (--stop-atr 2.0, TP at 1.5/2.5/4.0 ATR) and resolves each trade on
whichever level price reaches first. Forward return was the wrong measure:
a rule can leave price no higher yet still hold its stop far more often.
"""
import numpy as np
import MetaTrader5 as mt5

FWD_LIMIT = 96      # give a trade 8h on M5 to resolve before calling it open
STOP_ATR = 2.0      # matches the --stop-atr the scanner is run with
TP_ATR = (1.5, 2.5, 4.0)


def ema(a, n):
    k = 2 / (n + 1)
    o = np.empty_like(a)
    o[0] = a[0]
    for i in range(1, len(a)):
        o[i] = a[i] * k + o[i - 1] * (1 - k)
    return o


def atr_arr(h, l, c, n=14):
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    o = np.full(len(h), np.nan)
    for i in range(n, len(tr) + 1):
        o[i] = tr[i - n:i].mean()
    return o


def resolve(h, l, start, entry, stop, tps):
    """Walk forward; return which level is hit first. Stop wins a tied bar."""
    for j in range(start + 1, min(start + 1 + FWD_LIMIT, len(h))):
        if l[j] <= stop:
            return 'SL', j - start
        for name, price in zip(('TP3', 'TP2', 'TP1'), (tps[2], tps[1], tps[0])):
            if h[j] >= price:
                # report the furthest target reached on this bar
                return name, j - start
    return 'OPEN', FWD_LIMIT


def analyse(symbol, bars=5000):
    if not mt5.symbol_select(symbol, True):
        return None
    b = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    if b is None or len(b) < 500:
        return None
    c, h, l = b['close'].astype(float), b['high'].astype(float), b['low'].astype(float)
    e20, e50, a = ema(c, 20), ema(c, 50), atr_arr(h, l, c)
    zlo, zhi = e20 - 0.2 * a, e20 + 0.2 * a
    inside = (l <= zhi) & (h >= zlo) & ~np.isnan(a)
    up = e20 > e50

    touch, reclaim, crossings = [], [], []
    i = 60
    while i < len(c) - FWD_LIMIT - 1:
        if not (inside[i] and not inside[i - 1] and up[i]):
            i += 1
            continue

        # Rule A: enter at the close of the first touching candle.
        entry = c[i]
        stop = entry - STOP_ATR * a[i]
        tps = [entry + m * a[i] for m in TP_ATR]
        touch.append(resolve(h, l, i, entry, stop, tps))

        # Rule B: only after price closes back above the zone, having been
        # below it. Counts boundary crossings meanwhile to size the chop.
        j, went_below, crosses, above_prev = i, False, 0, None
        while j < len(c) - FWD_LIMIT - 1 and (j - i) <= 24:
            below = c[j] < zlo[j]
            above = c[j] > zhi[j]
            if below:
                went_below = True
            if above_prev is not None and above != above_prev and (below or above):
                crosses += 1
            if below or above:
                above_prev = above
            if went_below and above and up[j]:
                e = c[j]
                s = e - STOP_ATR * a[j]
                t = [e + m * a[j] for m in TP_ATR]
                reclaim.append(resolve(h, l, j, e, s, t))
                crossings.append(crosses)
                break
            j += 1
        i = j + 1 if j > i else i + 1
    return touch, reclaim, crossings


def summarise(rows, label):
    if not rows:
        return f'  {label:22s} n=0'
    n = len(rows)
    names = [r[0] for r in rows]
    sl = names.count('SL')
    tp1plus = sum(1 for x in names if x.startswith('TP'))
    # Exit-at-TP1 policy: +1.5R/2 = +0.75R per win, -1R per loss (stop = 2 ATR)
    r_tp1 = (tp1plus * (TP_ATR[0] / STOP_ATR) - sl) / n
    # Ladder policy: credit the furthest target actually reached
    credit = {'TP1': TP_ATR[0] / STOP_ATR, 'TP2': TP_ATR[1] / STOP_ATR,
              'TP3': TP_ATR[2] / STOP_ATR, 'SL': -1.0, 'OPEN': 0.0}
    r_ladder = sum(credit[x] for x in names) / n
    bars = np.mean([r[1] for r in rows])
    return (f'  {label:22s} n={n:4d}  TP-first {100*tp1plus/n:4.1f}%  SL-first {100*sl/n:4.1f}%'
            f'  expTP1 {r_tp1:+.3f}R  expLadder {r_ladder:+.3f}R  avg {bars:.0f} bars')


if __name__ == '__main__':
    if not mt5.initialize():
        raise SystemExit('MT5 init failed')
    try:
        for s in ['EURUSD', 'XAUUSD', 'GBPUSD',
                  'Volatility 75 (1s) Index', 'Volatility 10 (1s) Index']:
            out = analyse(s)
            if out is None:
                print(f'{s}: unavailable')
                continue
            touch, reclaim, crossings = out
            print(s)
            print(summarise(touch, 'enter on 1st touch'))
            print(summarise(reclaim, 'enter on reclaim'))
            if crossings:
                print(f'  {"zone crossings before reclaim":30s} mean {np.mean(crossings):.2f}'
                      f'  max {max(crossings)}  (chop indicator)')
            print()
    finally:
        mt5.shutdown()
