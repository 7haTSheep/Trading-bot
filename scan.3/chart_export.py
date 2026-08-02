"""Export the trade-critical levels of a scan for the MT5 chart indicator.

Python writes a small JSON file directly into the terminal's MQL5/Files
sandbox and the indicator reads it with plain file I/O. There is no HTTP
server, port, or bridge EA involved: this MT5 build blocks WebRequest from
indicators outright (GetLastError 4014), so a file drop is both simpler and
the only route that works without an intermediary.

Terminal output is unaffected -- this runs alongside it, never replaces it.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

FILENAME_PREFIX = 'chart_plan_'
PLAN_VERSION = '2.0'

# Roles the indicator knows how to draw. Colour and style for each is chosen
# on the MQL5 side so it stays user-configurable from the Inputs tab.
ROLE_ENTRY = 'ENTRY_ZONE'
ROLE_STOP = 'STOP_LOSS'
ROLE_TARGET = 'TARGET'
ROLE_SWING_HIGH = 'SWING_HIGH'
ROLE_SWING_LOW = 'SWING_LOW'


def _numbers(text: str) -> List[float]:
    """Pull floats out of a display string such as '7854.9-7865.9'."""
    return [float(match) for match in re.findall(r'\d+\.?\d*', str(text or ''))]


def _zone_bounds(text: str) -> Optional[Dict[str, float]]:
    values = _numbers(text)
    if not values:
        return None
    return {'low': min(values), 'high': max(values)}


def _level_price(panel_levels: Any, wanted_name: str) -> Optional[float]:
    """First numeric price of a named level in the chart marking panel."""
    for level in panel_levels:
        if getattr(level, 'name', '').strip().lower() == wanted_name.lower():
            values = _numbers(getattr(level, 'price_str', ''))
            if values:
                return values[0]
    return None


def plan_filename(symbol: str) -> str:
    """Per-symbol plan filename, e.g. 'chart_plan_Volatility_75__1s__Index.json'.

    One file per symbol so a multi-symbol scan doesn't have each symbol
    overwrite the last, and so an indicator on any chart can find its own
    plan. The indicator derives the identical name from its chart symbol, so
    this sanitising rule must stay byte-for-byte in step with the MQL5 side
    (QuickScanChart.mq5, PlanFileForSymbol): keep [A-Za-z0-9], everything
    else becomes '_'. Surrounding whitespace is stripped first, since a
    symbol typed on the command line may carry a stray trailing space that
    MT5's own symbol name will not have.
    """
    safe = ''.join(ch if ch.isalnum() and ch.isascii() else '_'
                   for ch in str(symbol).strip())
    return f'{FILENAME_PREFIX}{safe}.json'


def terminal_files_dir(mt5: Any) -> Optional[str]:
    """Locate the running terminal's MQL5/Files sandbox.

    Uses the live terminal_info() data_path rather than a hardcoded GUID so
    this keeps working across reinstalls and on another machine.
    """
    info = mt5.terminal_info()
    if info is None:
        return None
    data_path = getattr(info, 'data_path', '') or ''
    if not data_path:
        return None
    files_dir = os.path.join(data_path, 'MQL5', 'Files')
    return files_dir if os.path.isdir(files_dir) else None


def build_chart_plan(scan: Any) -> Dict[str, Any]:
    """Reduce a ScanResult to the trade-critical levels worth drawing."""
    decision = scan.decision_panel
    summary = scan.summary
    bias = 'BUY' if str(summary.bias).upper().startswith('BULL') else (
        'SELL' if str(summary.bias).upper().startswith('BEAR') else 'NEUTRAL')

    markings: List[Dict[str, Any]] = []

    zone_text = scan.entry_panel.ideal_sell_zone if bias == 'SELL' else scan.entry_panel.ideal_buy_zone
    zone = _zone_bounds(zone_text)
    if zone:
        markings.append({'role': ROLE_ENTRY, 'label': f'ENTRY {bias}',
                         'low': zone['low'], 'high': zone['high']})

    stop = getattr(scan.risk_panel.dynamic_stop, 'price', None)
    if stop:
        markings.append({'role': ROLE_STOP, 'label': 'SL', 'price': float(stop)})

    for target in scan.risk_panel.profit_targets[:3]:
        price = getattr(target, 'price', None)
        if price:
            markings.append({'role': ROLE_TARGET,
                             'label': str(getattr(target, 'name', 'TP')),
                             'price': float(price)})

    levels = getattr(scan.chart_marking_panel, 'levels', [])
    swing_high = _level_price(levels, 'Swing High')
    if swing_high:
        markings.append({'role': ROLE_SWING_HIGH, 'label': 'SWING HIGH', 'price': swing_high})
    swing_low = _level_price(levels, 'Swing Low')
    if swing_low:
        markings.append({'role': ROLE_SWING_LOW, 'label': 'SWING LOW', 'price': swing_low})

    return {
        'plan_version': PLAN_VERSION,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'symbol': scan.symbol,
        'bid': float(scan.bid),
        'bias': bias,
        'decision': decision.decision,
        'grade': decision.grade,
        'score': int(decision.entry_quality_score),
        'confidence': decision.confidence,
        'trend': scan.market_structure_panel.trend_strength,
        'phase': scan.market_structure_panel.market_phase,
        'reason': decision.reason,
        'markings': markings,
    }


def write_chart_plan(scan: Any, mt5: Any, filename: Optional[str] = None) -> Optional[str]:
    """Write the plan into MQL5/Files. Returns the path written, else None.

    Never raises: chart export is a display convenience and must not be able
    to take down a scan that already produced valid terminal output.
    """
    try:
        files_dir = terminal_files_dir(mt5)
        if not files_dir:
            return None
        plan = build_chart_plan(scan)
        if filename is None:
            filename = plan_filename(scan.symbol)
        # Write via a temp file in the same folder, then replace, so the
        # indicator can never read a half-written file mid-poll.
        final_path = os.path.join(files_dir, filename)
        temp_path = final_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as handle:
            json.dump(plan, handle, allow_nan=False)
        os.replace(temp_path, final_path)
        return final_path
    except Exception:
        return None
