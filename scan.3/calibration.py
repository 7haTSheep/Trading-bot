"""Learns which signals are worth taking, from resolved outcomes.

Reads the outcome log and works out, per bucket of signals, what they
actually returned. A bucket is only allowed to change behaviour once it has
enough resolved trades and the result is far enough from zero to be
distinguishable from chance. Until then it reports and changes nothing.

That gate is the point of this module rather than an afterthought. The
measured gross edge on these instruments is roughly +0.005R to +0.084R, and
a 5,000-candle study during development said four of five instruments were
unprofitable and Volatility 10 uniquely good, which reversed completely at
20,000 candles. An adaptive layer without a sample-size gate would have
learned that reversal as fact, twice, in opposite directions.

Nothing here predicts the market. It measures what already happened and
declines to act when the measurement is too weak to trust.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import outcome_tracker

# Resolved trades a bucket needs before it may influence anything. Set from
# how badly the 130-setup sample misled during development; a few dozen
# trades cannot separate a 0.05R edge from noise.
MIN_SAMPLES = 200

# How far from zero the mean must sit, in standard errors, before the bucket
# is called. 1.96 is the usual 95% two-sided threshold.
CONFIDENCE_Z = 1.96

SCORE_BUCKETS = ((80, 84), (85, 89), (90, 94), (95, 100))


def _r_multiple(row: Dict[str, Any]) -> Optional[float]:
    """What the signal actually returned, in R. None if it never resolved."""
    outcome = row.get('outcome')
    entry, stop = row.get('entry'), row.get('stop')
    if not outcome or outcome in ('OPEN',) or entry is None or stop is None:
        return None
    risk = abs(float(entry) - float(stop))
    if risk <= 0:
        return None
    if outcome == outcome_tracker.OUTCOME_STOP:
        return -1.0
    if outcome == outcome_tracker.OUTCOME_EXPIRED:
        return 0.0
    target = (row.get('targets') or {}).get(outcome)
    if target is None:
        return None
    return abs(float(target) - float(entry)) / risk


def _score_bucket(score: Any) -> Optional[str]:
    try:
        value = int(score)
    except (TypeError, ValueError):
        return None
    for low, high in SCORE_BUCKETS:
        if low <= value <= high:
            return f'{low}-{high}'
    return None


def _summarise(values: List[float]) -> Dict[str, Any]:
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        stderr = math.sqrt(variance / n)
    else:
        stderr = float('inf')
    # A verdict is only issued when the sample is large enough AND the
    # interval clears zero; otherwise the honest answer is "not yet known".
    if n < MIN_SAMPLES:
        verdict = 'insufficient'
    elif mean + CONFIDENCE_Z * stderr < 0:
        verdict = 'negative'
    elif mean - CONFIDENCE_Z * stderr > 0:
        verdict = 'positive'
    else:
        verdict = 'inconclusive'
    return {'n': n, 'mean_r': mean, 'stderr': stderr, 'verdict': verdict,
            'wins': sum(1 for v in values if v > 0)}


def build(directory: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Per-symbol and per-score-bucket statistics from resolved signals."""
    rows = outcome_tracker.load_signals(directory)
    by_symbol: Dict[str, List[float]] = {}
    by_score: Dict[str, List[float]] = {}
    for row in rows:
        r = _r_multiple(row)
        if r is None:
            continue
        by_symbol.setdefault(str(row.get('symbol')), []).append(r)
        bucket = _score_bucket(row.get('score'))
        if bucket:
            by_score.setdefault(bucket, []).append(r)
    return {
        'symbol': {k: _summarise(v) for k, v in by_symbol.items()},
        'score': {k: _summarise(v) for k, v in by_score.items()},
    }


def should_suppress(symbol: str, score: Any,
                    directory: Optional[str] = None,
                    model: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[bool, str]:
    """Whether to skip this signal, and why.

    Suppresses only on a verdict of 'negative', which requires both a large
    enough sample and an interval that clears zero. Anything unproven is
    allowed through: the default is to leave behaviour alone, never to block
    on a hunch.
    """
    model = model if model is not None else build(directory)

    stats = model['symbol'].get(symbol)
    if stats and stats['verdict'] == 'negative':
        return True, (f'{symbol} has returned {stats["mean_r"]:+.3f}R over '
                      f'{stats["n"]} resolved trades')

    bucket = _score_bucket(score)
    stats = model['score'].get(bucket) if bucket else None
    if stats and stats['verdict'] == 'negative':
        return True, (f'score band {bucket} has returned {stats["mean_r"]:+.3f}R '
                      f'over {stats["n"]} resolved trades')

    return False, ''


def report(directory: Optional[str] = None) -> str:
    model = build(directory)
    lines: List[str] = []
    total = sum(s['n'] for s in model['symbol'].values())
    lines.append(f'Calibration from {total} resolved signal(s)')
    lines.append(f'A bucket needs {MIN_SAMPLES} resolved trades and a mean clear of zero '
                 f'by {CONFIDENCE_Z} standard errors before it changes anything.')
    lines.append('')

    for title, key in (('BY SYMBOL', 'symbol'), ('BY SCORE BAND', 'score')):
        lines.append(title)
        group = model[key]
        if not group:
            lines.append('   nothing resolved yet')
        else:
            lines.append(f'   {"bucket":28s}{"n":>5s}{"win%":>7s}{"meanR":>9s}{"+/-":>8s}  verdict')
            for name, s in sorted(group.items(), key=lambda kv: -kv[1]['n']):
                margin = CONFIDENCE_Z * s['stderr']
                margin_text = f'{margin:7.3f}' if math.isfinite(margin) else '      -'
                lines.append(f'   {name:28s}{s["n"]:5d}{100*s["wins"]/s["n"]:6.0f}%'
                             f'{s["mean_r"]:9.3f}{margin_text}  {s["verdict"]}')
        lines.append('')

    acting = [f'{k} ({v["mean_r"]:+.3f}R)' for k, v in
              list(model['symbol'].items()) + list(model['score'].items())
              if v['verdict'] == 'negative']
    lines.append('Currently suppressing: ' + (', '.join(acting) if acting else 'nothing'))
    if not acting:
        lines.append('No bucket has met the evidence bar, so signals are unchanged.')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(report())
