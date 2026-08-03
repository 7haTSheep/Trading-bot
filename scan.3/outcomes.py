"""Score logged signals against what price actually did, and report by grade.

Run this any time after the scanner has been logging signals:

    python outcomes.py            resolve what can be resolved, then report
    python outcomes.py --report   report only, no MT5 connection needed

Signals need bars after them before they can be scored, so a signal logged
minutes ago will stay OPEN until price has had time to reach something.
"""
import argparse
import sys

import outcome_tracker


def main():
    parser = argparse.ArgumentParser(description='Score logged signals against real outcomes')
    parser.add_argument('--report', action='store_true',
                        help='Only print the report; skip resolving against MT5')
    parser.add_argument('--max-bars', type=int, default=288,
                        help='Bars to follow a signal before calling it expired (default 288 = 1 day of M5)')
    args = parser.parse_args()

    if not args.report:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print('MT5 init failed -- use --report to read the log without resolving',
                  file=sys.stderr)
            sys.exit(1)
        try:
            counts = outcome_tracker.resolve_pending(mt5, mt5.TIMEFRAME_M5, max_bars=args.max_bars)
        finally:
            mt5.shutdown()
        if counts:
            summary = ', '.join(f'{name}={count}' for name, count in sorted(counts.items()))
            print(f'Newly resolved: {summary}\n')
        else:
            print('Nothing newly resolved.\n')

    print(outcome_tracker.report())


if __name__ == '__main__':
    main()
