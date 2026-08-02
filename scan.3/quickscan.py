"""
quickscan.py -- Institutional Trade Decision Engine & Technical Scanner for MT5.

Features:
- Professional Trade Decision Engine (BUY NOW, SELL NOW, WAIT FOR PULLBACK, WAIT FOR BREAKOUT, WAIT FOR CONFIRMATION, NO TRADE)
- 0-100 Weighted Entry Quality Scoring (Grade A+, A, B, C, Wait)
- Extended Pullback & Trend State Classifications
- Actionable Trading Instructions (Buy/Sell Zones, Confirmations Needed, R:R)
- Comprehensive Chart Marking Assistant (Support/Resistance, Swings, ORBs, Pivots, VWAP, EMAs, FVGs, OBs, Liquidity Pools)
- Dynamic Stop Loss Selection (Swing High/Low, ATR, ORB, Order Block, Liquidity Sweep)
- Multiple Profit Targets (TP1, TP2, TP3, Runner Target with Probability, R:R, and Hold Time)
- Trade Invalidation Triggers
- 8-Point Institutional Setup Checklist
- Institutional Context Engine (Market Phase, ADX Trend Strength, Liquidity Pools, Volatility Environment)
- Professional Executive Summary & Chart Visualization Guidance
- Modular Architecture: Panel Data Models suitable for CLI, JSON, or future Windows Desktop App integration
"""
import os
import sys
import argparse
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
import MetaTrader5 as mt5
from candle_monitor import CandleMonitor, is_timeframe_token, timeframe_spec

# ==============================================================================
# CONSTANTS & STYLING
# ==============================================================================
LONDON_HOUR = 7
NY_HOUR = 13
TIMEFRAMES = [('M5', mt5.TIMEFRAME_M5), ('M15', mt5.TIMEFRAME_M15), ('H1', mt5.TIMEFRAME_H1)]
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
# Countdown cadence when stdout is captured/piped and can't repaint a line.
STATUS_LINE_SECONDS = 60

ANSI_GREEN = '\033[92m'
ANSI_RED = '\033[91m'
ANSI_YELLOW = '\033[93m'
ANSI_BLUE = '\033[94m'
ANSI_CYAN = '\033[96m'
ANSI_BOLD = '\033[1m'
ANSI_RESET = '\033[0m'


def supports_color(stream=None):
    stream = stream or sys.stdout
    if not hasattr(stream, 'isatty') or not stream.isatty():
        return False
    return os.getenv('TERM') != 'dumb'


def colorize_text(text, stream=None):
    if not supports_color(stream):
        return text
    pattern = re.compile(r'\b(BULL|BEAR|BULLISH|BEARISH|BUY NOW|SELL NOW|YES|NO|WAIT|A\+|A|B|C)\b', re.IGNORECASE)

    def repl(match):
        label = match.group(0)
        upper = label.upper()
        if upper in {'BULL', 'BULLISH', 'BUY NOW', 'YES', 'A+', 'A'}:
            return f'{ANSI_GREEN}{label}{ANSI_RESET}'
        if upper in {'BEAR', 'BEARISH', 'SELL NOW', 'NO'}:
            return f'{ANSI_RED}{label}{ANSI_RESET}'
        if upper in {'WAIT', 'WAIT FOR PULLBACK', 'WAIT FOR BREAKOUT', 'WAIT FOR CONFIRMATION', 'B', 'C'}:
            return f'{ANSI_YELLOW}{label}{ANSI_RESET}'
        return label

    return pattern.sub(repl, text)


# ==============================================================================
# TECHNICAL INDICATORS & MARKET STRUCTURE HELPERS
# ==============================================================================
def ema(a: np.ndarray, n: int) -> np.ndarray:
    k = 2 / (n + 1)
    e = a[0]
    out = []
    for x in a:
        e = k * x + (1 - k) * e
        out.append(e)
    return np.array(out)


def rsi(c: np.ndarray, n: int = 14) -> float:
    if len(c) <= n:
        return float('nan')
    d = np.diff(c)
    up = np.where(d > 0, d, 0)
    dn = np.where(d < 0, -d, 0)
    if len(up) < n:
        return float('nan')
    ru = up[:n].mean()
    rd = dn[:n].mean()
    for i in range(n, len(d)):
        ru = (ru * (n - 1) + up[i]) / n
        rd = (rd * (n - 1) + dn[i]) / n
    return 100 - 100 / (1 + ru / max(rd, 1e-9))


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> float:
    if len(c) <= n:
        return float('nan')
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    if len(tr) < n:
        return float('nan')
    return tr[-n:].mean()


def adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> Tuple[float, float, float]:
    """Calculates Average Directional Index (ADX), +DI, -DI."""
    if len(c) < n + 1:
        return float('nan'), float('nan'), float('nan')

    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    up_move = h[1:] - h[:-1]
    down_move = l[:-1] - l[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    if len(tr) < n:
        return float('nan'), float('nan'), float('nan')

    tr_smooth = np.zeros(len(tr))
    plus_dm_smooth = np.zeros(len(tr))
    minus_dm_smooth = np.zeros(len(tr))

    tr_smooth[n - 1] = np.mean(tr[:n])
    plus_dm_smooth[n - 1] = np.mean(plus_dm[:n])
    minus_dm_smooth[n - 1] = np.mean(minus_dm[:n])

    for i in range(n, len(tr)):
        tr_smooth[i] = tr_smooth[i - 1] - (tr_smooth[i - 1] / n) + tr[i]
        plus_dm_smooth[i] = plus_dm_smooth[i - 1] - (plus_dm_smooth[i - 1] / n) + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i - 1] - (minus_dm_smooth[i - 1] / n) + minus_dm[i]

    plus_di = 100 * (plus_dm_smooth / np.maximum(tr_smooth, 1e-9))
    minus_di = 100 * (minus_dm_smooth / np.maximum(tr_smooth, 1e-9))

    dx = 100 * np.abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-9)

    if len(dx) < 2 * n:
        adx_val = np.mean(dx[n - 1:])
    else:
        adx_val = np.mean(dx[-n:])

    return float(adx_val), float(plus_di[-1]), float(minus_di[-1])


def rsi_flag(r: float) -> str:
    if np.isnan(r):
        return ''
    if r >= RSI_OVERBOUGHT:
        return ' (OVERBOUGHT)'
    if r <= RSI_OVERSOLD:
        return ' (OVERSOLD)'
    return ''


def stack_label(e20: float, e50: float, e200: float) -> str:
    if np.isnan(e20) or np.isnan(e50) or np.isnan(e200):
        return 'MIXED'
    if e20 > e50 > e200:
        return 'BULL'
    if e20 < e50 < e200:
        return 'BEAR'
    return 'MIXED'


def compute_confluence_score(tf_data: dict) -> Tuple[int, str]:
    """Assigns +1 per Bullish timeframe, -1 per Bearish timeframe (-3 to +3)."""
    score = 0
    for tf in ['M5', 'M15', 'H1']:
        st = tf_data.get(tf, {}).get('stack', 'MIXED')
        if st == 'BULL':
            score += 1
        elif st == 'BEAR':
            score -= 1

    if score == 3:
        desc = '+3 (Strong Bull)'
    elif score == 2:
        desc = '+2 (Moderate Bull)'
    elif score == 1:
        desc = '+1 (Weak Bull)'
    elif score == 0:
        desc = '0 (Neutral / Mixed)'
    elif score == -1:
        desc = '-1 (Weak Bear)'
    elif score == -2:
        desc = '-2 (Moderate Bear)'
    elif score == -3:
        desc = '-3 (Strong Bear)'
    else:
        desc = f'{score:+d}'
    return score, desc


def compute_volatility_context(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14, lookback: int = 50) -> dict:
    """Compares current M5 ATR against a rolling 50-period mean ATR."""
    if len(c) < n + lookback:
        return {'atr': float('nan'), 'ratio': 1.0, 'label': 'NORMAL'}

    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    if len(tr) < n + lookback:
        return {'atr': float('nan'), 'ratio': 1.0, 'label': 'NORMAL'}

    current_atr = tr[-n:].mean()
    atr_hist = [tr[i - n:i].mean() for i in range(len(tr) - lookback + 1, len(tr) + 1)]
    avg_atr = np.mean(atr_hist) if atr_hist else current_atr

    ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
    if ratio >= 1.3:
        label = f'HIGH ({ratio:.1f}x avg - wide stops expected)'
    elif ratio <= 0.7:
        label = f'LOW ({ratio:.1f}x avg - tight compression)'
    else:
        label = f'NORMAL ({ratio:.1f}x avg)'

    return {'atr': current_atr, 'ratio': ratio, 'label': label}


def detect_divergence(c: np.ndarray, rsi_series: np.ndarray, window: int = 30) -> Optional[str]:
    """Scans recent window of M5 bars for Bullish or Bearish RSI Divergence."""
    if len(c) < window or len(rsi_series) < window or np.isnan(rsi_series[-1]):
        return None
    c_sub = c[-window:]
    rsi_sub = rsi_series[-window:]

    low_indices = [i for i in range(1, len(c_sub) - 1) if c_sub[i] < c_sub[i - 1] and c_sub[i] < c_sub[i + 1]]
    high_indices = [i for i in range(1, len(c_sub) - 1) if c_sub[i] > c_sub[i - 1] and c_sub[i] > c_sub[i + 1]]

    if len(low_indices) >= 2:
        i1, i2 = low_indices[-2], low_indices[-1]
        if c_sub[i2] < c_sub[i1] and rsi_sub[i2] > rsi_sub[i1]:
            return 'BULLISH DIVERGENCE (Price Lower Low, RSI Higher Low)'

    if len(high_indices) >= 2:
        i1, i2 = high_indices[-2], high_indices[-1]
        if c_sub[i2] > c_sub[i1] and rsi_sub[i2] < rsi_sub[i1]:
            return 'BEARISH DIVERGENCE (Price Higher High, RSI Lower High)'

    return None


def compute_pivot_points(sym: str) -> dict:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 2)
    if rates is None or len(rates) < 2:
        return {'P': None, 'R1': None, 'S1': None, 'prev_high': None, 'prev_low': None}
    prev = rates[-2]
    h, l, c = prev['high'], prev['low'], prev['close']
    p = (h + l + c) / 3.0
    r1 = (2.0 * p) - l
    s1 = (2.0 * p) - h
    return {'P': p, 'R1': r1, 'S1': s1, 'prev_high': h, 'prev_low': l}


def compute_vwap(r_m5: Any, server_now: datetime) -> Optional[float]:
    if r_m5 is None or len(r_m5) == 0:
        return None
    today_start = server_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = today_start.timestamp()

    tp_vol_sum = 0.0
    vol_sum = 0.0
    names = r_m5.dtype.names if hasattr(r_m5, 'dtype') and r_m5.dtype.names else ()
    for x in r_m5:
        if x['time'] >= today_ts:
            tp = (x['high'] + x['low'] + x['close']) / 3.0
            vol = 0
            if 'real_volume' in names:
                vol = x['real_volume']
            if vol == 0 and 'tick_volume' in names:
                vol = x['tick_volume']
            if vol > 0:
                tp_vol_sum += tp * vol
                vol_sum += vol
    if vol_sum > 0:
        return tp_vol_sum / vol_sum
    return None


# ==============================================================================
# ADVANCED PRICE ACTION / SMART MONEY CALCULATIONS
# ==============================================================================
def detect_fair_value_gaps(h: np.ndarray, l: np.ndarray, c: np.ndarray, window: int = 30) -> Dict[str, Any]:
    """Detects recent Fair Value Gaps (FVG) and Inverse Fair Value Gaps (IFVG)."""
    bullish_fvgs = []
    bearish_fvgs = []
    if len(c) < 3:
        return {'bullish': [], 'bearish': []}

    start_idx = max(0, len(c) - window)
    for i in range(start_idx, len(c) - 2):
        # Bullish FVG: Low of bar i+2 > High of bar i
        if l[i + 2] > h[i]:
            gap_low = h[i]
            gap_high = l[i + 2]
            filled = False
            for j in range(i + 3, len(c)):
                if l[j] <= gap_low:
                    filled = True
                    break
            if not filled:
                bullish_fvgs.append({'low': gap_low, 'high': gap_high, 'mid': (gap_low + gap_high) / 2.0})

        # Bearish FVG: High of bar i+2 < Low of bar i
        if h[i + 2] < l[i]:
            gap_high = l[i]
            gap_low = h[i + 2]
            filled = False
            for j in range(i + 3, len(c)):
                if h[j] >= gap_high:
                    filled = True
                    break
            if not filled:
                bearish_fvgs.append({'low': gap_low, 'high': gap_high, 'mid': (gap_low + gap_high) / 2.0})

    return {'bullish': bullish_fvgs, 'bearish': bearish_fvgs}


def detect_order_blocks(h: np.ndarray, l: np.ndarray, c: np.ndarray, window: int = 40) -> Dict[str, Any]:
    """Identifies Bullish and Bearish Order Blocks."""
    bullish_obs = []
    bearish_obs = []
    if len(c) < 5:
        return {'bullish': [], 'bearish': []}

    start_idx = max(0, len(c) - window)
    for i in range(start_idx, len(c) - 3):
        # Bullish OB: Bearish candle followed by strong bullish move
        if c[i] < c[max(0, i - 1)] and c[i + 2] > h[i]:
            bullish_obs.append({'low': l[i], 'high': h[i], 'price': (l[i] + h[i]) / 2.0})
        # Bearish OB: Bullish candle followed by strong bearish move
        if c[i] > c[max(0, i - 1)] and c[i + 2] < l[i]:
            bearish_obs.append({'low': l[i], 'high': h[i], 'price': (l[i] + h[i]) / 2.0})

    return {
        'bullish': bullish_obs[-2:] if bullish_obs else [],
        'bearish': bearish_obs[-2:] if bearish_obs else []
    }


def detect_liquidity_pools(h: np.ndarray, l: np.ndarray, atr_val: float, window: int = 50) -> Dict[str, Any]:
    """Identifies Equal Highs (EQH) and Equal Lows (EQL) liquidity pools."""
    if len(h) < window or np.isnan(atr_val) or atr_val <= 0:
        return {'eqh': None, 'eql': None}

    h_sub = h[-window:]
    l_sub = l[-window:]

    highs = [h_sub[i] for i in range(1, len(h_sub) - 1) if h_sub[i] > h_sub[i - 1] and h_sub[i] > h_sub[i + 1]]
    lows = [l_sub[i] for i in range(1, len(l_sub) - 1) if l_sub[i] < l_sub[i - 1] and l_sub[i] < l_sub[i + 1]]

    eqh = None
    if len(highs) >= 2:
        sorted_highs = sorted(highs, reverse=True)
        if abs(sorted_highs[0] - sorted_highs[1]) <= 0.2 * atr_val:
            eqh = (sorted_highs[0] + sorted_highs[1]) / 2.0

    eql = None
    if len(lows) >= 2:
        sorted_lows = sorted(lows)
        if abs(sorted_lows[1] - sorted_lows[0]) <= 0.2 * atr_val:
            eql = (sorted_lows[0] + sorted_lows[1]) / 2.0

    return {'eqh': eqh, 'eql': eql}


# ==============================================================================
# MODULAR PANEL DATA MODELS (WINDOWS APP COMPATIBILITY LAYER)
# ==============================================================================
@dataclass
class TradeDecisionPanel:
    decision: str
    icon: str
    reason: str
    entry_quality_score: int
    grade: str
    confidence: str


@dataclass
class EntryPanel:
    current_status: str
    detailed_classification: str
    reason: str
    ideal_buy_zone: str
    ideal_sell_zone: str
    confirmation_needed: List[str]
    expected_rr: float


@dataclass
class DynamicStopInfo:
    price: float
    distance_pts: float
    method: str
    reason: str


@dataclass
class ProfitTargetItem:
    name: str
    price: float
    rr: float
    probability_pct: int
    expected_holding_time: str


@dataclass
class RiskPanel:
    dynamic_stop: DynamicStopInfo
    profit_targets: List[ProfitTargetItem]
    optimal_lot: float
    min_lot_risk_dollars: float
    min_lot_risk_pct: float
    fits_account: bool
    action_status: str


@dataclass
class ChartMarkingLevel:
    name: str
    price_str: str
    priority: str
    reason: str


@dataclass
class ChartMarkingPanel:
    levels: List[ChartMarkingLevel]
    visual_guidance: List[str]


@dataclass
class ChecklistItem:
    name: str
    status: str


@dataclass
class TradeChecklistPanel:
    items: List[ChecklistItem]


@dataclass
class MarketStructurePanel:
    trend_strength: str
    momentum_strength: str
    liquidity_location: str
    volatility_environment: str
    market_phase: str
    adx_val: float
    premium_zone: str
    discount_zone: str
    support: Optional[float]
    resistance: Optional[float]


@dataclass
class ProfessionalSummary:
    bias: str
    trade: str
    entry: str
    stop: float
    tp1: float
    tp2: float
    tp3: float
    confidence: str
    grade: str
    risk: str
    best_action: str


@dataclass
class ScanResult:
    symbol: str
    bid: float
    ask: float
    spread: float
    decision_panel: TradeDecisionPanel
    entry_panel: EntryPanel
    risk_panel: RiskPanel
    chart_marking_panel: ChartMarkingPanel
    checklist_panel: TradeChecklistPanel
    market_structure_panel: MarketStructurePanel
    summary: ProfessionalSummary

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# ENTRY STATE & PULLBACK CLASSIFICATION
# ==============================================================================
def classify_entry_state(price: float, ema20: float, atr: Optional[float] = None, rsi: Optional[float] = None,
                         trend: str = 'NEUTRAL', swing_high: Optional[float] = None,
                         swing_low: Optional[float] = None, orb_high: Optional[float] = None,
                         orb_low: Optional[float] = None, atr_val: Optional[float] = None,
                         rsi_val: Optional[float] = None) -> str:
    """
    Mathematical rules for state machine:
    - BREAKOUT: Price within 1.0 ATR beyond ORB high/low or swing high/low.
    - EXTENDED: Price >= 1.5 ATR beyond ORB high/low boundary or EMA20.
    - PULLBACK: Price near EMA20 (within 0.3 ATR) or ORB boundary holding above/below range.
    - EXHAUSTED: RSI >= 75 (bull) or RSI <= 25 (bear).
    - NEUTRAL: None of the above conditions met.
    """
    effective_atr = atr if atr is not None else (atr_val if atr_val is not None else float('nan'))
    effective_rsi = rsi if rsi is not None else (rsi_val if rsi_val is not None else 50.0)

    states = []
    if effective_atr is None or np.isnan(effective_atr) or effective_atr <= 0:
        return 'NEUTRAL'

    if trend == 'BULL':
        ref_level = orb_high if orb_high is not None else ema20
        if price - ref_level >= 1.5 * effective_atr or price - ema20 >= 1.5 * effective_atr:
            states.append('extended')

        if orb_high is not None and price >= orb_high and (price - orb_high) <= 1.0 * effective_atr:
            states.append('breakout')
        elif swing_high is not None and price >= swing_high and (price - swing_high) <= 1.0 * effective_atr:
            if 'extended' not in states:
                states.append('breakout')

        if abs(price - ema20) <= 0.3 * effective_atr or (orb_high is not None and price >= orb_high and (price - orb_high) <= 0.3 * effective_atr):
            if 'extended' not in states:
                states.append('pullback')

        if effective_rsi >= 75:
            states.append('exhausted')

    elif trend == 'BEAR':
        ref_level = orb_low if orb_low is not None else ema20
        if ref_level - price >= 1.5 * effective_atr or ema20 - price >= 1.5 * effective_atr:
            states.append('extended')

        if orb_low is not None and price <= orb_low and (orb_low - price) <= 1.0 * effective_atr:
            states.append('breakout')
        elif swing_low is not None and price <= swing_low and (swing_low - price) <= 1.0 * effective_atr:
            if 'extended' not in states:
                states.append('breakout')


        if abs(price - ema20) <= 0.3 * effective_atr or (orb_low is not None and price <= orb_low and (orb_low - price) <= 0.3 * effective_atr):
            if 'extended' not in states:
                states.append('pullback')

        if effective_rsi <= 25:
            states.append('exhausted')

    if not states:
        return 'neutral'
    return '/'.join(states)



def entry_state_label(state: str, trend: Optional[str] = None) -> str:
    label = state.lower()
    prefix = 'BULLISH' if trend == 'BULL' else 'BEARISH' if trend == 'BEAR' else ''

    parts = []
    if 'breakout' in label:
        parts.append('BREAKOUT')
    if 'pullback' in label:
        parts.append('PULLBACK')
    if 'extended' in label:
        parts.append('EXTENDED')
    if 'exhausted' in label:
        parts.append('EXHAUSTED')

    if parts:
        return f'{prefix} {"/".join(parts)}'.strip()
    return 'NEUTRAL'


def entry_state_icon(state: str, trend: Optional[str] = None) -> str:
    label = state.lower()
    if 'extended' in label and 'exhausted' in label:
        return '🟡🔴'
    if 'extended' in label:
        return '🟡'
    if 'exhausted' in label:
        return '🔴'
    if 'pullback' in label:
        return '🟢'
    if 'breakout' in label:
        return '🔵'
    return '⚪'


def classify_detailed_pullback(trend: str, price: float, ema20: float, ema50: float, atr_val: float,
                               rsi_val: float, state: str) -> str:
    """Provides detailed institutional pullback classification."""
    label = state.lower()
    if trend == 'BULL':
        if 'breakout' in label:
            return 'Fresh Breakout'
        if rsi_val >= 75:
            return 'Exhaustion Risk'
        if 'extended' in label:
            return 'Late Trend'
        if abs(price - ema20) <= 0.25 * atr_val:
            return 'EMA20 Retest'
        if abs(price - ema50) <= 0.35 * atr_val:
            return 'EMA50 Retest'
        if 'pullback' in label:
            return 'Healthy Pullback'
        if rsi_val > 60:
            return 'High Momentum'
        return 'Healthy Pullback'
    elif trend == 'BEAR':
        if 'breakout' in label:
            return 'Fresh Breakdown'
        if rsi_val <= 25:
            return 'Exhaustion Risk'
        if 'extended' in label:
            return 'Late Trend'
        if abs(price - ema20) <= 0.25 * atr_val:
            return 'EMA20 Rejection'
        if abs(price - ema50) <= 0.35 * atr_val:
            return 'EMA50 Rejection'
        if 'pullback' in label:
            return 'Healthy Pullback'
        if rsi_val < 40:
            return 'Momentum Selloff'
        return 'Healthy Pullback'
    return 'Neutral / Ranging'


# ==============================================================================
# OPENING RANGE (ORB) COMPUTATION
# ==============================================================================
def opening_range(sym: str, server_now: datetime, hour: int, tf_minutes: int = 5, range_bars: int = 3) -> dict:
    session_open = server_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if server_now < session_open:
        time_diff = session_open - server_now
        hrs, mins = divmod(int(time_diff.total_seconds()), 3600)
        mins, _ = divmod(mins, 60)
        return {'status': 'not_open', 'hi': None, 'lo': None, 'width': None, 'broke': None, 'pending_in': f'{hrs}h{mins}m'}
    end = session_open + timedelta(minutes=tf_minutes * range_bars)
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, session_open, end)
    if r is None or len(r) < range_bars:
        return {'status': 'forming', 'hi': None, 'lo': None, 'width': None, 'broke': None, 'pending_in': None}
    rng_hi = max(x['high'] for x in r[:range_bars])
    rng_lo = min(x['low'] for x in r[:range_bars])
    tick = mt5.symbol_info_tick(sym)
    bid = tick.bid if tick else 0.0
    broke = 'above' if bid > rng_hi else ('below' if bid < rng_lo else 'inside')
    return {'status': 'established', 'hi': rng_hi, 'lo': rng_lo, 'width': rng_hi - rng_lo, 'broke': broke, 'pending_in': None}


def opening_range_str(o: dict, hour: int) -> str:
    if o['status'] == 'not_open':
        pending = f" (opens in {o['pending_in']})" if o.get('pending_in') else ""
        return f'{hour:02d}:00 session not open yet today{pending}'
    if o['status'] == 'forming':
        return f'{hour:02d}:00 session: range still forming / insufficient bars'
    return (f'{hour:02d}:00 range hi={o["hi"]:.5g} lo={o["lo"]:.5g} width={o["width"]:.5g} '
            f'-> price is {o["broke"].upper()}')


# ==============================================================================
# ENTRY QUALITY SCORER (0-100)
# ==============================================================================
def calculate_entry_quality_score(tf_data: dict, confluence_score: int, price: float, ema20: float,
                                   ema50: float, atr_val: float, vwap_val: Optional[float],
                                   london: dict, ny: dict, rsi_val: float, adx_val: float,
                                   vol_ratio: float, trend: str) -> Tuple[int, str, str, Dict[str, int]]:
    """
    Weighted Entry Quality Score (0–100):
    - Trend Alignment: 30 pts
    - Confluence: 20 pts
    - EMA Pullback: 15 pts
    - VWAP Position: 10 pts
    - ORB Confirmation: 10 pts
    - Momentum (RSI/ADX): 10 pts
    - Volatility Context: 5 pts
    """
    scores = {}

    # 1. Trend Alignment (30 pts max)
    stacks = [d.get('stack', 'MIXED') for d in tf_data.values()]
    aligned_ct = stacks.count('BULL') if trend == 'BULL' else (stacks.count('BEAR') if trend == 'BEAR' else 0)
    if aligned_ct == 3:
        scores['trend'] = 30
    elif aligned_ct == 2:
        scores['trend'] = 20
    elif aligned_ct == 1:
        scores['trend'] = 10
    else:
        scores['trend'] = 0

    # 2. Confluence (20 pts max)
    scores['confluence'] = int((abs(confluence_score) / 3.0) * 20)

    # 3. EMA Pullback (15 pts max)
    if not np.isnan(ema20) and atr_val > 0:
        dist_ema20 = abs(price - ema20) / atr_val
        if dist_ema20 <= 0.3:
            scores['ema_pullback'] = 15
        elif dist_ema20 <= 0.6:
            scores['ema_pullback'] = 10
        elif dist_ema20 >= 1.5:
            scores['ema_pullback'] = 0
        else:
            scores['ema_pullback'] = 7
    else:
        scores['ema_pullback'] = 7

    # 4. VWAP Position (10 pts max)
    if vwap_val is not None:
        if trend == 'BULL' and price >= vwap_val:
            scores['vwap'] = 10
        elif trend == 'BEAR' and price <= vwap_val:
            scores['vwap'] = 10
        elif abs(price - vwap_val) <= 0.5 * (atr_val or 1.0):
            scores['vwap'] = 6
        else:
            scores['vwap'] = 2
    else:
        scores['vwap'] = 5

    # 5. ORB Confirmation (10 pts max)
    orb_confirmed = False
    for o in [london, ny]:
        if o.get('status') == 'established':
            if trend == 'BULL' and o.get('broke') == 'above':
                orb_confirmed = True
            elif trend == 'BEAR' and o.get('broke') == 'below':
                orb_confirmed = True
    if orb_confirmed:
        scores['orb'] = 10
    elif any(o.get('status') == 'established' for o in [london, ny]):
        scores['orb'] = 5
    else:
        scores['orb'] = 5

    # 6. Momentum (RSI/ADX) (10 pts max)
    rsi_pts = 5
    if trend == 'BULL':
        if 45 <= rsi_val <= 68:
            rsi_pts = 5
        elif rsi_val > 75:
            rsi_pts = 1
        else:
            rsi_pts = 3
    elif trend == 'BEAR':
        if 32 <= rsi_val <= 55:
            rsi_pts = 5
        elif rsi_val < 25:
            rsi_pts = 1
        else:
            rsi_pts = 3

    adx_pts = 5 if adx_val >= 25 else (3 if adx_val >= 18 else 1)
    scores['momentum'] = rsi_pts + adx_pts

    # 7. Volatility Context (5 pts max)
    if 0.8 <= vol_ratio <= 1.3:
        scores['volatility'] = 5
    elif vol_ratio < 0.8:
        scores['volatility'] = 3
    else:
        scores['volatility'] = 2

    total_score = min(100, max(0, sum(scores.values())))

    if total_score >= 90:
        grade = 'A+ (Institutional Setup)'
        confidence = 'High'
    elif total_score >= 80:
        grade = 'A Setup'
        confidence = 'High'
    elif total_score >= 70:
        grade = 'B Setup'
        confidence = 'Medium'
    elif total_score >= 60:
        grade = 'C Setup'
        confidence = 'Low'
    else:
        grade = 'Wait'
        confidence = 'Low'

    return total_score, grade, confidence, scores


# ==============================================================================
# TRADE DECISION ENGINE
# ==============================================================================
def determine_trade_decision(trend: str, quality_score: int, price: float, ema20: float,
                            atr_val: float, state: str, rsi_val: float,
                            confluence_score: int) -> Tuple[str, str, str]:
    """
    Decisions: BUY NOW, SELL NOW, WAIT FOR PULLBACK, WAIT FOR BREAKOUT, WAIT FOR CONFIRMATION, NO TRADE
    """
    label = state.lower()
    dist_ema20_pts = (price - ema20) if not np.isnan(ema20) else 0.0

    if quality_score >= 80:
        if trend == 'BULL':
            if 'extended' in label or rsi_val >= 75:
                return 'WAIT FOR PULLBACK', '🟡', (f'Price is extended ({abs(dist_ema20_pts):.1f} pts above M5 EMA20). '
                                                  f'Entering now has poor risk-to-reward. Wait for retracement into value zone.')
            if 'breakout' in label:
                return 'BUY NOW', '🟢', f'Fresh Bullish Breakout confirmed with high entry quality ({quality_score}/100).'
            return 'BUY NOW', '🟢', f'Bullish alignment in value zone (M5 EMA20) with quality score of {quality_score}/100.'
        elif trend == 'BEAR':
            if 'extended' in label or rsi_val <= 25:
                return 'WAIT FOR PULLBACK', '🟡', (f'Price is extended ({abs(dist_ema20_pts):.1f} pts below M5 EMA20). '
                                                  f'Entering now has poor risk-to-reward. Wait for retracement into value zone.')
            if 'breakout' in label:
                return 'SELL NOW', '🔴', f'Fresh Bearish Breakdown confirmed with high entry quality ({quality_score}/100).'
            return 'SELL NOW', '🔴', f'Bearish rejection from M5 EMA20 in value zone with quality score of {quality_score}/100.'

    if quality_score >= 65:
        if 'extended' in label:
            return 'WAIT FOR PULLBACK', '🟡', (f'Price is extended from EMA20 ({abs(dist_ema20_pts):.1f} pts). '
                                              f'Wait for a retracement into the value zone.')
        if 'breakout' in label:
            return 'WAIT FOR BREAKOUT', '🟡', 'Price testing breakout boundary. Wait for a candle close beyond structure.'
        return 'WAIT FOR CONFIRMATION', '🟠', (f'Moderate setup quality ({quality_score}/100). '
                                             f'Wait for explicit candlestick rejection or M5 momentum confirmation.')

    if abs(confluence_score) == 0:
        return 'NO TRADE', '🔴', 'Conflicting timeframe signals (M5, M15, H1 not aligned). Market is choppy.'

    return 'NO TRADE', '🔴', f'Entry Quality Score ({quality_score}/100) is below acceptable institutional threshold (70+).'


# ==============================================================================
# DYNAMIC STOP LOSS & PROFIT TARGET ENGINES
# ==============================================================================
def calculate_dynamic_stop(trend: str, price: float, atr_val: float, swing_high: Optional[float],
                           swing_low: Optional[float], london: dict, ny: dict,
                           order_blocks: dict, stop_atr_mult: float) -> DynamicStopInfo:
    """Intelligently selects highest probability stop loss location."""
    candidates = []

    if trend == 'BULL' and swing_low and swing_low < price:
        dist = price - swing_low + (0.2 * (atr_val or 0))
        candidates.append((dist, swing_low - (0.2 * (atr_val or 0)), 'Below Swing Low',
                           'Placing stop below recent swing low structure provides high probability noise protection.'))
    elif trend == 'BEAR' and swing_high and swing_high > price:
        dist = swing_high - price + (0.2 * (atr_val or 0))
        candidates.append((dist, swing_high + (0.2 * (atr_val or 0)), 'Above Swing High',
                           'Placing stop above recent swing high structure provides high probability noise protection.'))

    for label_orb, o in [('London', london), ('NY', ny)]:
        if o.get('status') == 'established' and o.get('width'):
            if trend == 'BULL' and o.get('lo'):
                dist = price - o['lo'] + (0.1 * (atr_val or 0))
                candidates.append((dist, o['lo'] - (0.1 * (atr_val or 0)), f'Beyond {label_orb} ORB Low',
                                   f'Placing stop invalidates {label_orb} Opening Range Breakout structure.'))
            elif trend == 'BEAR' and o.get('hi'):
                dist = o['hi'] - price + (0.1 * (atr_val or 0))
                candidates.append((dist, o['hi'] + (0.1 * (atr_val or 0)), f'Beyond {label_orb} ORB High',
                                   f'Placing stop invalidates {label_orb} Opening Range Breakdown structure.'))

    if trend == 'BULL' and order_blocks.get('bullish'):
        ob_low = order_blocks['bullish'][-1]['low']
        if ob_low < price:
            dist = price - ob_low + (0.1 * (atr_val or 0))
            candidates.append((dist, ob_low - (0.1 * (atr_val or 0)), 'Below Bullish Order Block',
                               'Placing stop beneath demand order block invalidates institutional support.'))
    elif trend == 'BEAR' and order_blocks.get('bearish'):
        ob_high = order_blocks['bearish'][-1]['high']
        if ob_high > price:
            dist = ob_high - price + (0.1 * (atr_val or 0))
            candidates.append((dist, ob_high + (0.1 * (atr_val or 0)), 'Above Bearish Order Block',
                               'Placing stop above supply order block invalidates institutional resistance.'))

    atr_dist = stop_atr_mult * (atr_val or 1.0)
    atr_stop_price = price - atr_dist if trend != 'BEAR' else price + atr_dist
    candidates.append((atr_dist, atr_stop_price, 'ATR Dynamic Volatility Stop',
                       f'Generic {stop_atr_mult}x M5 ATR volatility stop applied as safe fallback.'))

    valid_candidates = [c for c in candidates if 0.5 * atr_val <= c[0] <= 3.0 * atr_val]
    chosen = valid_candidates[0] if valid_candidates else candidates[-1]

    return DynamicStopInfo(
        price=chosen[1],
        distance_pts=chosen[0],
        method=chosen[2],
        reason=chosen[3]
    )


def calculate_profit_targets(trend: str, price: float, stop_dist: float, atr_val: float,
                            swing_high: Optional[float], swing_low: Optional[float],
                            pivots: dict) -> List[ProfitTargetItem]:
    """Calculates multiple profit targets (TP1, TP2, TP3, Runner)."""
    targets = []
    if stop_dist <= 0 or np.isnan(stop_dist):
        stop_dist = 2.0 * (atr_val or 1.0)

    is_bull = trend != 'BEAR'

    tp1_dist = 1.5 * (atr_val or 1.0)
    tp1_price = price + tp1_dist if is_bull else price - tp1_dist
    if is_bull and swing_high and swing_high > price and swing_high < tp1_price:
        tp1_price = swing_high
    elif not is_bull and swing_low and swing_low < price and swing_low > tp1_price:
        tp1_price = swing_low
    rr1 = abs(tp1_price - price) / stop_dist
    targets.append(ProfitTargetItem('TP1', tp1_price, rr1, 80, '~15-30m'))

    tp2_dist = 2.5 * (atr_val or 1.0)
    tp2_price = price + tp2_dist if is_bull else price - tp2_dist
    if is_bull and pivots.get('R1') and pivots['R1'] > price:
        tp2_price = pivots['R1']
    elif not is_bull and pivots.get('S1') and pivots['S1'] < price:
        tp2_price = pivots['S1']
    rr2 = abs(tp2_price - price) / stop_dist
    targets.append(ProfitTargetItem('TP2', tp2_price, rr2, 60, '~45-90m'))

    tp3_dist = 4.0 * (atr_val or 1.0)
    tp3_price = price + tp3_dist if is_bull else price - tp3_dist
    rr3 = abs(tp3_price - price) / stop_dist
    targets.append(ProfitTargetItem('TP3', tp3_price, rr3, 40, '~2-4h'))

    runner_dist = 6.0 * (atr_val or 1.0)
    runner_price = price + runner_dist if is_bull else price - runner_dist
    rr_runner = abs(runner_price - price) / stop_dist
    targets.append(ProfitTargetItem('Runner Target', runner_price, rr_runner, 25, 'Intraday/Swing'))

    return targets


# ==============================================================================
# CHART MARKING ASSISTANT & VISUALIZATION GUIDANCE
# ==============================================================================
def generate_chart_markings(price: float, swing_high: Optional[float], swing_low: Optional[float],
                            london: dict, ny: dict, pivots: dict, vwap_val: Optional[float],
                            e20: float, e50: float, e200: float, fvgs: dict, order_blocks: dict,
                            liquidity: dict, atr_val: float) -> Tuple[List[ChartMarkingLevel], List[str]]:
    levels = []
    guidance = []

    if swing_high:
        levels.append(ChartMarkingLevel('Swing High', f'{swing_high:.5g}', 'High' if swing_high > price else 'Medium', 'Recent M5 Swing High Structure'))
        guidance.append(f'Mark swing high: {swing_high:.5g}')
    if swing_low:
        levels.append(ChartMarkingLevel('Swing Low', f'{swing_low:.5g}', 'High' if swing_low < price else 'Medium', 'Recent M5 Swing Low Structure'))
        guidance.append(f'Mark swing low: {swing_low:.5g}')

    for name_orb, o in [('London ORB', london), ('NY ORB', ny)]:
        if o.get('status') == 'established':
            levels.append(ChartMarkingLevel(f'{name_orb} High', f'{o["hi"]:.5g}', 'High', 'Session Opening Range High'))
            levels.append(ChartMarkingLevel(f'{name_orb} Low', f'{o["lo"]:.5g}', 'High', 'Session Opening Range Low'))

    if pivots.get('P'):
        levels.append(ChartMarkingLevel('Daily Pivot (P)', f'{pivots["P"]:.5g}', 'Medium', 'Daily Central Pivot Point'))
    if pivots.get('R1'):
        levels.append(ChartMarkingLevel('Daily Resistance (R1)', f'{pivots["R1"]:.5g}', 'High', 'First Daily Resistance Target'))
        guidance.append(f'Draw resistance at: {pivots["R1"]:.5g}')
    if pivots.get('S1'):
        levels.append(ChartMarkingLevel('Daily Support (S1)', f'{pivots["S1"]:.5g}', 'High', 'First Daily Support Level'))
        guidance.append(f'Draw support at: {pivots["S1"]:.5g}')

    if vwap_val:
        levels.append(ChartMarkingLevel('Intraday VWAP', f'{vwap_val:.5g}', 'High', 'Volume Weighted Average Price Benchmark'))

    if not np.isnan(e20):
        levels.append(ChartMarkingLevel('M5 EMA20', f'{e20:.5g}', 'High', 'Primary dynamic pullback/value area'))
        guidance.append(f'Draw EMA20 reaction zone: {e20 - 0.2*atr_val:.5g}–{e20 + 0.2*atr_val:.5g}')
    if not np.isnan(e50):
        levels.append(ChartMarkingLevel('M5 EMA50', f'{e50:.5g}', 'Medium', 'Secondary trend baseline support/resistance'))

    for fvg in fvgs.get('bullish', []):
        levels.append(ChartMarkingLevel('Bullish FVG', f'{fvg["low"]:.5g}–{fvg["high"]:.5g}', 'High', 'Unfilled institutional buying imbalance'))
        guidance.append(f'Highlight Bullish FVG: {fvg["low"]:.5g}–{fvg["high"]:.5g}')
    for fvg in fvgs.get('bearish', []):
        levels.append(ChartMarkingLevel('Bearish FVG', f'{fvg["low"]:.5g}–{fvg["high"]:.5g}', 'High', 'Unfilled institutional selling imbalance'))
        guidance.append(f'Highlight Bearish FVG: {fvg["low"]:.5g}–{fvg["high"]:.5g}')

    for ob in order_blocks.get('bullish', []):
        levels.append(ChartMarkingLevel('Bullish Order Block', f'{ob["low"]:.5g}–{ob["high"]:.5g}', 'High', 'Institutional demand block'))
    for ob in order_blocks.get('bearish', []):
        levels.append(ChartMarkingLevel('Bearish Order Block', f'{ob["low"]:.5g}–{ob["high"]:.5g}', 'High', 'Institutional supply block'))

    if liquidity.get('eqh'):
        levels.append(ChartMarkingLevel('Liquidity Pool (EQH)', f'{liquidity["eqh"]:.5g}', 'High', 'Equal Highs Liquidity Pool (Buy Stop Liquidity)'))
        guidance.append(f'Mark liquidity pool: Above {liquidity["eqh"]:.5g}')
    if liquidity.get('eql'):
        levels.append(ChartMarkingLevel('Liquidity Pool (EQL)', f'{liquidity["eql"]:.5g}', 'High', 'Equal Lows Liquidity Pool (Sell Stop Liquidity)'))
        guidance.append(f'Mark liquidity pool: Below {liquidity["eql"]:.5g}')

    if swing_high and swing_low and swing_high > swing_low:
        mid = (swing_high + swing_low) / 2.0
        levels.append(ChartMarkingLevel('Premium Zone', f'{mid:.5g}–{swing_high:.5g}', 'Medium', 'Upper 50% Range (Sell Value Zone)'))
        levels.append(ChartMarkingLevel('Discount Zone', f'{swing_low:.5g}–{mid:.5g}', 'Medium', 'Lower 50% Range (Buy Value Zone)'))
        guidance.append(f'Mark premium zone: {mid:.5g}–{swing_high:.5g}')
        guidance.append(f'Mark discount zone: {swing_low:.5g}–{mid:.5g}')

    return levels, guidance


# ==============================================================================
# SETUP CHECKLIST & TRADE INVALIDATION
# ==============================================================================
def build_setup_checklist(trend: str, confluence_score: int, london: dict, ny: dict,
                          vwap_val: Optional[float], price: float, ema20: float,
                          rsi_val: float, adx_val: float, liquidity: dict,
                          fits_account: bool, quality_score: int) -> List[ChecklistItem]:
    items = []
    items.append(ChecklistItem('Trend aligned', 'YES' if abs(confluence_score) >= 2 else ('WAIT' if abs(confluence_score) == 1 else 'NO')))
    orb_brk = any(o.get('status') == 'established' and o.get('broke') in ('above', 'below') for o in [london, ny])
    items.append(ChecklistItem('ORB broken', 'YES' if orb_brk else 'WAIT'))
    vwap_ok = (vwap_val is not None) and ((trend == 'BULL' and price >= vwap_val) or (trend == 'BEAR' and price <= vwap_val))
    items.append(ChecklistItem('VWAP confirmed', 'YES' if vwap_ok else 'NO'))
    ema_ok = abs(price - ema20) <= 0.6 * (abs(price - ema20) or 1.0) if not np.isnan(ema20) else False
    items.append(ChecklistItem('EMA rejection', 'YES' if ema_ok else 'WAIT'))
    mom_ok = (adx_val >= 20) and ((trend == 'BULL' and rsi_val >= 45) or (trend == 'BEAR' and rsi_val <= 55))
    items.append(ChecklistItem('Momentum confirmed', 'YES' if mom_ok else 'NO'))
    items.append(ChecklistItem('Liquidity available', 'YES' if liquidity.get('eqh') or liquidity.get('eql') else 'WAIT'))
    items.append(ChecklistItem('Risk acceptable', 'YES' if fits_account else 'NO'))
    items.append(ChecklistItem('Entry confirmed', 'YES' if quality_score >= 70 else 'WAIT'))

    return items


def generate_trade_invalidation(trend: str, ema50: float, vwap_val: Optional[float],
                                rsi_val: float, london: dict, ny: dict) -> List[str]:
    reasons = []
    if trend == 'BEAR':
        if not np.isnan(ema50):
            reasons.append(f'Price closes above M5 EMA50 ({ema50:.5g})')
        if vwap_val:
            reasons.append(f'Price reclaims Intraday VWAP ({vwap_val:.5g})')
        reasons.append('M5 RSI exceeds 55.0')
        for label, o in [('London', london), ('NY', ny)]:
            if o.get('status') == 'established' and o.get('hi'):
                reasons.append(f'{label} ORB High is reclaimed ({o["hi"]:.5g})')
                break
    else:
        if not np.isnan(ema50):
            reasons.append(f'Price closes below M5 EMA50 ({ema50:.5g})')
        if vwap_val:
            reasons.append(f'Price loses Intraday VWAP ({vwap_val:.5g})')
        reasons.append('M5 RSI drops below 45.0')
        for label, o in [('London', london), ('NY', ny)]:
            if o.get('status') == 'established' and o.get('lo'):
                reasons.append(f'{label} ORB Low is lost ({o["lo"]:.5g})')
                break

    return reasons if reasons else ['Price invalidates structural swing boundary']


# ==============================================================================
# MAIN SCANNER CORE FUNCTION
# ==============================================================================
def scan_symbol(sym: str, risk_pct: float, stop_atr_mult: float, equity: Optional[float],
                compare_rows: Optional[list] = None, summary_rows: Optional[list] = None) -> Optional[ScanResult]:
    if not mt5.symbol_select(sym, True):
        if compare_rows is not None:
            compare_rows.append((sym, 'NOT AVAILABLE', '', '', '', '', ''))
        if summary_rows is not None:
            summary_rows.append((sym, 'N/A', 'UNAVAILABLE', 'N/A', 'N/A', 'N/A', '❌ NOT AVAILABLE'))
        else:
            print(f'\n=== {sym} === NOT AVAILABLE on this account')
        return None

    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None or tick.bid == 0:
        if compare_rows is not None:
            compare_rows.append((sym, 'NO DATA', '', '', '', '', ''))
        if summary_rows is not None:
            summary_rows.append((sym, 'NO DATA', 'NO DATA', 'N/A', 'N/A', 'N/A', '❌ NO DATA'))
        else:
            print(f'\n=== {sym} === no live data')
        return None

    tf_data = {}
    m5_atr = None
    m5_r = None
    m5_c = None
    m5_h = None
    m5_l = None
    m5_rsi_series = None

    for tfname, tf in TIMEFRAMES:
        r = mt5.copy_rates_from_pos(sym, tf, 0, 300)
        if r is None or len(r) < 60:
            continue
        c = np.array([x['close'] for x in r])
        h = np.array([x['high'] for x in r])
        l = np.array([x['low'] for x in r])
        e20, e50, e200 = ema(c, 20)[-1], ema(c, 50)[-1], ema(c, 200)[-1]
        _rsi = rsi(c)
        _atr = atr(h, l, c)
        stack = stack_label(e20, e50, e200)
        tf_data[tfname] = {'close': c[-1], 'e20': e20, 'e50': e50, 'e200': e200,
                           'stack': stack, 'rsi': _rsi, 'atr': _atr}
        if tfname == 'M5':
            m5_atr = _atr
            m5_r = r
            m5_c = c
            m5_h = h
            m5_l = l
            rsi_hist = [rsi(c[:i + 1]) for i in range(15, len(c))]
            m5_rsi_series = np.array([float('nan')] * 15 + rsi_hist)

    server_now = datetime.fromtimestamp(tick.time)
    london = opening_range(sym, server_now, LONDON_HOUR)
    ny = opening_range(sym, server_now, NY_HOUR)

    vol_ctx = compute_volatility_context(m5_h, m5_l, m5_c) if m5_c is not None else {'label': 'NORMAL', 'ratio': 1.0, 'atr': m5_atr or 1.0}
    pivots = compute_pivot_points(sym)
    vwap_val = compute_vwap(m5_r, server_now)
    confluence_score, confluence_desc = compute_confluence_score(tf_data)

    m5_swing_high = max((x['high'] for x in m5_r[-20:]), default=None) if m5_r is not None else None
    m5_swing_low = min((x['low'] for x in m5_r[-20:]), default=None) if m5_r is not None else None
    orb_high = max((o['hi'] for o in [london, ny] if o.get('status') == 'established' and o.get('hi') is not None), default=None)
    orb_low = min((o['lo'] for o in [london, ny] if o.get('status') == 'established' and o.get('lo') is not None), default=None)

    m5_e20 = tf_data.get('M5', {}).get('e20', float('nan')) if 'M5' in tf_data else float('nan')
    m5_e50 = tf_data.get('M5', {}).get('e50', float('nan')) if 'M5' in tf_data else float('nan')
    m5_e200 = tf_data.get('M5', {}).get('e200', float('nan')) if 'M5' in tf_data else float('nan')
    m5_rsi_val = tf_data.get('M5', {}).get('rsi', 50.0) if 'M5' in tf_data else 50.0

    trend = stack_label(m5_e20, m5_e50, m5_e200)

    entry_state = classify_entry_state(
        price=tick.bid,
        ema20=m5_e20,
        atr_val=m5_atr or 1.0,
        rsi_val=m5_rsi_val,
        trend=trend,
        swing_high=m5_swing_high,
        swing_low=m5_swing_low,
        orb_high=orb_high,
        orb_low=orb_low,
    )
    detailed_pullback = classify_detailed_pullback(trend, tick.bid, m5_e20, m5_e50, m5_atr or 1.0, m5_rsi_val, entry_state)

    adx_val, plus_di, minus_di = adx(m5_h, m5_l, m5_c) if m5_c is not None else (20.0, 20.0, 20.0)
    fvgs = detect_fair_value_gaps(m5_h, m5_l, m5_c) if m5_c is not None else {'bullish': [], 'bearish': []}
    order_blocks = detect_order_blocks(m5_h, m5_l, m5_c) if m5_c is not None else {'bullish': [], 'bearish': []}
    liquidity = detect_liquidity_pools(m5_h, m5_l, m5_atr or 1.0) if m5_h is not None else {'eqh': None, 'eql': None}

    quality_score, grade, confidence, score_breakdown = calculate_entry_quality_score(
        tf_data=tf_data,
        confluence_score=confluence_score,
        price=tick.bid,
        ema20=m5_e20,
        ema50=m5_e50,
        atr_val=m5_atr or 1.0,
        vwap_val=vwap_val,
        london=london,
        ny=ny,
        rsi_val=m5_rsi_val,
        adx_val=adx_val,
        vol_ratio=vol_ctx.get('ratio', 1.0),
        trend=trend
    )

    decision, decision_icon, decision_reason = determine_trade_decision(
        trend=trend,
        quality_score=quality_score,
        price=tick.bid,
        ema20=m5_e20,
        atr_val=m5_atr or 1.0,
        state=entry_state,
        rsi_val=m5_rsi_val,
        confluence_score=confluence_score
    )

    dynamic_stop = calculate_dynamic_stop(
        trend=trend,
        price=tick.bid,
        atr_val=m5_atr or 1.0,
        swing_high=m5_swing_high,
        swing_low=m5_swing_low,
        london=london,
        ny=ny,
        order_blocks=order_blocks,
        stop_atr_mult=stop_atr_mult
    )

    profit_targets = calculate_profit_targets(
        trend=trend,
        price=tick.bid,
        stop_dist=dynamic_stop.distance_pts,
        atr_val=m5_atr or 1.0,
        swing_high=m5_swing_high,
        swing_low=m5_swing_low,
        pivots=pivots
    )

    fits_account = True
    loss_per_min_lot = 0.0
    minlot_pct_eq = 0.0
    optimal_lot = 0.0
    action_status = '⏳ MONITOR'

    if equity and info.trade_tick_size and info.trade_tick_value:
        loss_per_min_lot = dynamic_stop.distance_pts / info.trade_tick_size * info.trade_tick_value * info.volume_min
        minlot_pct_eq = loss_per_min_lot / equity * 100
        risk_money = equity * risk_pct / 100
        loss_per_lot = dynamic_stop.distance_pts / info.trade_tick_size * info.trade_tick_value
        optimal_lot = risk_money / loss_per_lot if loss_per_lot > 0 else 0.0
        stepped_lot = np.floor(optimal_lot / info.volume_step) * info.volume_step if info.volume_step else optimal_lot
        optimal_lot = max(info.volume_min, stepped_lot)
        fits_account = stepped_lot >= info.volume_min

        if fits_account:
            if decision in ('BUY NOW', 'SELL NOW'):
                action_status = f'⚡ {decision}'
            elif decision.startswith('WAIT'):
                action_status = f'🟢 FIT ({decision})'
            else:
                action_status = '🟢 FIT'
        else:
            action_status = '❌ SKIP (under min lot)'

    buy_zone = f'{m5_e20 - 0.2*(m5_atr or 1.0):.5g}–{m5_e20 + 0.2*(m5_atr or 1.0):.5g}' if not np.isnan(m5_e20) else f'{tick.bid:.5g}'
    sell_zone = f'{m5_e20 - 0.2*(m5_atr or 1.0):.5g}–{m5_e20 + 0.2*(m5_atr or 1.0):.5g}' if not np.isnan(m5_e20) else f'{tick.bid:.5g}'
    confirmations_needed = ['Bullish engulfing candle', 'Strong rejection wick', 'Higher low on M5', 'RSI turns upward'] if trend == 'BULL' else ['Bearish engulfing candle', 'Upper rejection wick', 'Lower high on M5', 'RSI turns downward']

    levels, visual_guidance = generate_chart_markings(
        price=tick.bid,
        swing_high=m5_swing_high,
        swing_low=m5_swing_low,
        london=london,
        ny=ny,
        pivots=pivots,
        vwap_val=vwap_val,
        e20=m5_e20,
        e50=m5_e50,
        e200=m5_e200,
        fvgs=fvgs,
        order_blocks=order_blocks,
        liquidity=liquidity,
        atr_val=m5_atr or 1.0
    )

    checklist_items = build_setup_checklist(
        trend=trend,
        confluence_score=confluence_score,
        london=london,
        ny=ny,
        vwap_val=vwap_val,
        price=tick.bid,
        ema20=m5_e20,
        rsi_val=m5_rsi_val,
        adx_val=adx_val,
        liquidity=liquidity,
        fits_account=fits_account,
        quality_score=quality_score
    )

    invalidation_reasons = generate_trade_invalidation(
        trend=trend,
        ema50=m5_e50,
        vwap_val=vwap_val,
        rsi_val=m5_rsi_val,
        london=london,
        ny=ny
    )

    trend_str = 'Strong Bullish' if confluence_score == 3 else ('Moderate Bullish' if confluence_score > 0 else ('Strong Bearish' if confluence_score == -3 else 'Ranging / Mixed'))
    mom_str = f'{"High" if adx_val >= 25 else "Moderate"} (RSI: {m5_rsi_val:.1f} | ADX: {adx_val:.1f})'
    liq_str = 'Sweeping Discount Liquidity' if trend == 'BULL' else 'Sweeping Premium Liquidity'
    phase_str = 'Expansion Phase (Trending)' if adx_val >= 25 else 'Compression Phase (Ranging)'

    decision_panel = TradeDecisionPanel(
        decision=decision,
        icon=decision_icon,
        reason=decision_reason,
        entry_quality_score=quality_score,
        grade=grade,
        confidence=confidence
    )

    entry_panel = EntryPanel(
        current_status=decision,
        detailed_classification=detailed_pullback,
        reason=decision_reason,
        ideal_buy_zone=buy_zone,
        ideal_sell_zone=sell_zone,
        confirmation_needed=confirmations_needed,
        expected_rr=profit_targets[0].rr if profit_targets else 1.5
    )

    risk_panel = RiskPanel(
        dynamic_stop=dynamic_stop,
        profit_targets=profit_targets,
        optimal_lot=optimal_lot,
        min_lot_risk_dollars=loss_per_min_lot,
        min_lot_risk_pct=minlot_pct_eq,
        fits_account=fits_account,
        action_status=action_status
    )

    chart_marking_panel = ChartMarkingPanel(levels=levels, visual_guidance=visual_guidance)
    checklist_panel = TradeChecklistPanel(items=checklist_items)

    premium_zone_str = f'{(m5_swing_low or tick.bid):.5g}–{(m5_swing_high or tick.bid):.5g}'
    discount_zone_str = f'{(m5_swing_low or tick.bid):.5g}–{(m5_swing_high or tick.bid):.5g}'

    market_structure_panel = MarketStructurePanel(
        trend_strength=trend_str,
        momentum_strength=mom_str,
        liquidity_location=liq_str,
        volatility_environment=vol_ctx['label'],
        market_phase=phase_str,
        adx_val=adx_val,
        premium_zone=premium_zone_str,
        discount_zone=discount_zone_str,
        support=pivots.get('S1'),
        resistance=pivots.get('R1')
    )

    summary = ProfessionalSummary(
        bias=f'{trend} ({confluence_desc})',
        trade=decision,
        entry=buy_zone if trend == 'BULL' else sell_zone,
        stop=dynamic_stop.price,
        tp1=profit_targets[0].price if profit_targets else 0.0,
        tp2=profit_targets[1].price if len(profit_targets) > 1 else 0.0,
        tp3=profit_targets[2].price if len(profit_targets) > 2 else 0.0,
        confidence=confidence,
        grade=grade,
        risk='Low' if fits_account else 'High',
        best_action=decision_reason
    )

    result = ScanResult(
        symbol=sym,
        bid=tick.bid,
        ask=tick.ask,
        spread=tick.ask - tick.bid,
        decision_panel=decision_panel,
        entry_panel=entry_panel,
        risk_panel=risk_panel,
        chart_marking_panel=chart_marking_panel,
        checklist_panel=checklist_panel,
        market_structure_panel=market_structure_panel,
        summary=summary
    )

    if compare_rows is not None:
        h1 = tf_data.get('H1', {})
        bias_short = build_verdict(tf_data, london, ny).replace('VERDICT: ', '') if tf_data else 'n/a'
        compare_rows.append((
            sym,
            f'{tick.bid:.5g}',
            f'{tick.ask - tick.bid:.4g}',
            f'{h1.get("rsi", float("nan")):.1f}' if h1 else '',
            colorize_text(bias_short),
            f'{minlot_pct_eq:.1f}%',
            'OK' if fits_account else 'BELOW MIN',
        ))

    if summary_rows is not None:
        tp_str = f'{summary.tp1:.5g} / {summary.tp2:.5g}'
        rr_str = f'{profit_targets[0].rr:.2f}:1' if profit_targets else 'N/A'
        summary_rows.append((
            sym,
            f'{confluence_desc}',
            f'{entry_state_icon(entry_state, trend=trend)} {detailed_pullback}',
            vol_ctx['label'].split()[0],
            tp_str,
            rr_str,
            action_status,
        ))

    if compare_rows is None:
        print_detailed_scan(result, london, ny, pivots, vwap_val, tf_data, confluence_desc,
                            vol_ctx, invalidation_reasons, risk_pct, stop_atr_mult, equity, info)

    return result


def build_verdict(tf_data: dict, london: dict, ny: dict) -> str:
    stacks = [d['stack'] for d in tf_data.values()]
    bull_ct = stacks.count('BULL')
    bear_ct = stacks.count('BEAR')
    if bull_ct == len(stacks):
        bias = 'BULL (all timeframes aligned)'
    elif bear_ct == len(stacks):
        bias = 'BEAR (all timeframes aligned)'
    elif bull_ct > bear_ct:
        bias = f'lean BULL ({bull_ct}/{len(stacks)} aligned, rest mixed)'
    elif bear_ct > bull_ct:
        bias = f'lean BEAR ({bear_ct}/{len(stacks)} aligned, rest mixed)'
    else:
        bias = 'NO CLEAR BIAS (conflicting timeframes)'

    h1_rsi = tf_data.get('H1', {}).get('rsi')
    rsi_note = ''
    if h1_rsi is not None and not np.isnan(h1_rsi):
        if h1_rsi >= RSI_OVERBOUGHT:
            rsi_note = ', H1 RSI overbought -- late to chase longs'
        elif h1_rsi <= RSI_OVERSOLD:
            rsi_note = ', H1 RSI oversold -- late to chase shorts'

    session_note = ''
    for label, o in [('London', london), ('NY', ny)]:
        if o['status'] == 'established' and o['broke'] in ('above', 'below'):
            session_note += f', {label} ORB broke {o["broke"]}'

    return f'VERDICT: {bias}{rsi_note}{session_note}'


# ==============================================================================
# CLI PRESENTATION & SUMMARY TABLES
# ==============================================================================
def print_detailed_scan(r: ScanResult, london: dict, ny: dict, pivots: dict, vwap_val: Optional[float],
                        tf_data: dict, confluence_desc: str, vol_ctx: dict,
                        invalidation_reasons: List[str], risk_pct: float, stop_atr_mult: float,
                        equity: Optional[float], info: Any) -> None:
    print('\n' + '=' * 80)
    print(f'=== {r.symbol} === (Bid: {r.bid:.5g} | Ask: {r.ask:.5g} | Spread: {r.spread:.6g})')
    print('=' * 80)

    dp = r.decision_panel
    print(colorize_text(f'\n1. TRADE DECISION LAYER\n   Decision: {dp.icon} {dp.decision}\n   Reason  : {dp.reason}'))

    print(colorize_text(f'\n2. ENTRY QUALITY SCORE\n   Entry Quality: {dp.entry_quality_score}/100\n   Grade        : {dp.grade}\n   Confidence   : {dp.confidence}'))

    ep = r.entry_panel
    print(colorize_text(f'\n3. PULLBACK & STATE CLASSIFICATION\n   Classification: {ep.detailed_classification}'))

    print(colorize_text(f'\n4. ACTIONABLE TRADING INSTRUCTIONS\n   Current Status     : {ep.current_status}\n   Ideal Buy Zone     : {ep.ideal_buy_zone}\n   Ideal Sell Zone    : {ep.ideal_sell_zone}\n   Confirmation Needed: {", ".join(ep.confirmation_needed)}\n   Expected R:R       : {ep.expected_rr:.2f}:1'))

    cmp = r.chart_marking_panel
    print('\n5. CHART MARKING ASSISTANT\n   MARK THESE LEVELS:')
    for lvl in cmp.levels[:15]:
        print(f'   - {lvl.name.ljust(22)}: {lvl.price_str.ljust(18)} [Priority: {lvl.priority.ljust(6)}] ({lvl.reason})')

    print(colorize_text(f'\n6. ENTRY ZONE GENERATOR\n   Buy Zone   : {ep.ideal_buy_zone}\n   Sell Zone  : {ep.ideal_sell_zone}\n   Confidence : {dp.entry_quality_score}%\n   Risk Level : {r.summary.risk}'))

    rp = r.risk_panel
    ds = rp.dynamic_stop
    print(f'\n7. DYNAMIC STOP LOSS\n   Stop Loss : {ds.price:.5g} (Distance: {ds.distance_pts:.5g} pts)\n   Method    : {ds.method}\n   Rationale : {ds.reason}')

    print('\n8. MULTIPLE PROFIT TARGETS')
    for tp in rp.profit_targets:
        print(f'   - {tp.name.ljust(13)}: {tp.price:.5g} (Prob: {tp.probability_pct}%, R:R: {tp.rr:.2f}:1, Est Hold: {tp.expected_holding_time})')

    print('\n9. TRADE INVALIDATION\n   Thesis fails if:')
    for inv in invalidation_reasons:
        print(f'   - {inv}')

    cp = r.checklist_panel
    print('\n10. SETUP CHECKLIST')
    for chk in cp.items:
        print(colorize_text(f'   [{chk.status.ljust(4)}] {chk.name}'))

    mp = r.market_structure_panel
    print(f'\n11. INSTITUTIONAL CONTEXT\n   Trend Strength    : {mp.trend_strength}\n   Momentum Strength : {mp.momentum_strength}\n   Liquidity Location: {mp.liquidity_location}\n   Volatility Env    : {mp.volatility_environment}\n   Market Phase      : {mp.market_phase}')

    s = r.summary
    print(colorize_text(f'\n12. PROFESSIONAL SUMMARY\n   Bias      : {s.bias}\n   Trade     : {s.trade}\n   Entry     : {s.entry}\n   Stop      : {s.stop:.5g}\n   TP1 / TP2 : {s.tp1:.5g} / {s.tp2:.5g}\n   TP3       : {s.tp3:.5g}\n   Confidence: {s.confidence} ({dp.entry_quality_score}%)\n   Grade     : {s.grade}\n   Best Action: {s.best_action}'))

    print('\n13. CHART VISUALIZATION GUIDANCE')
    for g in cmp.visual_guidance[:8]:
        print(f'   -> {g}')


def print_compare_table(rows: list) -> None:
    headers = ['Symbol', 'Bid', 'Spread', 'H1 RSI', 'Verdict', 'MinLot%Eq', 'Fits?']
    widths = [max(len(str(r[i])) for r in ([headers] + rows)) for i in range(len(headers))]
    def fmt_row(r):
        return '  '.join(str(c).ljust(w) for c, w in zip(r, widths))
    print(fmt_row(headers))
    print('  '.join('-' * w for w in widths))
    for r in rows:
        print(fmt_row(r))


def print_master_summary(summary_rows: list) -> None:
    headers = ['Symbol', 'Bias & Confluence', 'Entry State & Pullback', 'Volatility', 'TP1 / TP2 Target', 'R:R (TP1)', 'Action']
    widths = [max(len(str(r[i])) for r in ([headers] + summary_rows)) for i in range(len(headers))]
    def fmt_row(r):
        return '  '.join(str(c).ljust(w) for c, w in zip(r, widths))

    print('\n' + '=' * 80)
    print(' MASTER SUMMARY SNAPSHOT')
    print('=' * 80)
    print(fmt_row(headers))
    print('  '.join('-' * w for w in widths))
    for r in summary_rows:
        print(fmt_row(r))
    print('=' * 80)


def parse_interval_seconds(token: str) -> Optional[int]:
    match = re.fullmatch(r'(\d+)([smhd])', token.strip().lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == 's':
        return value
    if unit == 'm':
        return value * 60
    if unit == 'h':
        return value * 60 * 60
    if unit == 'd':
        return value * 60 * 60 * 24
    return None


def run_scan_cycle(args, equity, symbols=None):
    """Run one full analysis pass over the requested symbols."""
    symbols = symbols if symbols is not None else args.symbols
    summary_rows = []
    if args.compare:
        rows = []
        for sym in symbols:
            scan_symbol(sym, args.risk, args.stop_atr, equity,
                        compare_rows=rows, summary_rows=summary_rows)
        print()
        print_compare_table(rows)
    else:
        for sym in symbols:
            scan_symbol(sym, args.risk, args.stop_atr, equity, summary_rows=summary_rows)
    if len(symbols) > 1 and not args.compare:
        print_master_summary(summary_rows)


def run_candle_event_mode(args, equity, spec):
    """Analyse on real candle-close events instead of a fixed sleep timer.

    A sleep timer drifts out of alignment with actual candle boundaries and
    can analyse a partially-formed bar; watching the bar's identity change
    guarantees exactly one analysis per closed candle, using closed data only.
    """
    monitors = {sym: CandleMonitor(mt5, sym, spec) for sym in args.symbols}
    for monitor in monitors.values():
        monitor.initialize()

    live_countdown = supports_color()
    print(f'\nCandle-event mode: {spec["label"]} | Symbols: {", ".join(args.symbols)}')
    print('Analysis runs once per candle close (Ctrl+C to stop)\n')

    # Immediate first read so the session doesn't start with a blind wait.
    run_scan_cycle(args, equity)

    primary = next(iter(monitors.values()))
    last_status_second = -1
    while True:
        triggered = [sym for sym, monitor in monitors.items()
                     if monitor.new_closed_candle() is not None]
        if triggered:
            closed_id = monitors[triggered[0]].last_processed_candle
            stamp = CandleMonitor.format_candle_time(closed_id)
            print(f'\n{"=" * 80}')
            print(f'{spec["label"]} CANDLE CLOSED at {stamp} -> {", ".join(triggered)}')
            print(f'{"=" * 80}')
            # In compare mode the table covers every symbol at once, so a
            # single trigger should refresh the whole set, not one column.
            run_scan_cycle(args, equity, symbols=None if args.compare else triggered)
            if args.compare:
                # The table already covered every symbol; drain any sibling
                # that rolled over a moment later so one bar transition can't
                # print the whole table twice.
                for monitor in monitors.values():
                    monitor.new_closed_candle()
            last_status_second = -1
            continue

        now_second = int(time.time())
        if now_second != last_status_second:
            last_status_second = now_second
            remaining = primary.seconds_remaining()
            status = (f'Next {spec["label"]} close in {CandleMonitor.format_countdown(remaining)}'
                      f'  (candle opened {CandleMonitor.format_candle_time(primary.current_candle_time)})')
            if live_countdown:
                # Real terminal: rewind and repaint the same line each second.
                print(f'\r  {status}   ', end='', flush=True)
            elif now_second % STATUS_LINE_SECONDS == 0:
                # Captured/piped output ignores \r, so a per-second repaint
                # would append hundreds of lines instead of overwriting one.
                print(f'  {status}', flush=True)
        time.sleep(1.0)


def main():
    argv = sys.argv[1:]
    interval_seconds = None
    candle_token = None
    if argv:
        last_token = argv[-1]
        if is_timeframe_token(last_token):
            candle_token = last_token
            argv = argv[:-1]
        else:
            parsed_interval = parse_interval_seconds(last_token)
            if parsed_interval is not None:
                interval_seconds = parsed_interval
                argv = argv[:-1]

    p = argparse.ArgumentParser(description='Institutional MT5 Technical + Trade Decision Engine')
    p.add_argument('symbols', nargs='*', help='Symbol name(s), quote multi-word names')
    p.add_argument('--risk', type=float, default=5.0, help='Risk %% of equity for lot calc (default 5)')
    p.add_argument('--stop-atr', type=float, default=2.0, help='Stop distance as multiple of M5 ATR fallback (default 2.0)')
    p.add_argument('--compare', action='store_true', help='Compact side-by-side table instead of full detail per symbol')
    args = p.parse_args(argv)

    if not args.symbols:
        p.error('at least one symbol is required')

    if not mt5.initialize():
        print('MT5 init failed', file=sys.stderr)
        sys.exit(1)

    try:
        acct = mt5.account_info()
        if acct:
            print(f'Account: login={acct.login} server={acct.server} equity=${acct.equity} balance=${acct.balance}')
        equity = acct.equity if acct else None

        if candle_token is not None:
            run_candle_event_mode(args, equity, timeframe_spec(candle_token, mt5))
            return

        while True:
            run_scan_cycle(args, equity)

            if interval_seconds is None:
                break

            print(f'\nNext scan in {interval_seconds}s (Ctrl+C to stop)')
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print('\nStopped by user')
    finally:
        mt5.shutdown()


if __name__ == '__main__':
    main()

