QuickScan.py — Institutional MT5 Trade Decision Engine & Scanner
quickscan.py is a professional command-line Trade Decision Engine and multi-symbol market scanner for MetaTrader 5 (MT5), specifically optimized for Synthetic Indices (Deriv) and Forex.

Rather than simply reporting whether the market is bullish or bearish, quickscan.py acts as a professional discretionary trader, evaluating setups and answering:

Should I trade right now? (BUY NOW, SELL NOW, WAIT FOR PULLBACK, NO TRADE)
What grade is this setup? (0–100 score; Grades A+, A, B, C)
Where is the safest entry, stop loss, and profit targets? (TP1, TP2, TP3 with hit probabilities and R:R)
What exact chart markings should I place on MT5?
What invalidates this trade thesis?
1. Prerequisites
Operating System: Windows (MetaTrader 5 Native API requirement)
Python: Python 3.10 or higher installed
MetaTrader 5 Terminal: Installed, running, and logged into your trading account (e.g. Deriv, IC Markets, Exness).
Dependencies: Install required Python packages:
cmd

pip install MetaTrader5 numpy
2. Command Line Syntax & Usage
cmd

python quickscan.py [SYMBOLS...] [FLAGS] [INTERVAL]
IMPORTANT

Always place quotes around multi-word symbol names (e.g. "Volatility 75 (1s) Index").

3. How to Run quickscan.py
A. Single Symbol Detailed Scan
Scan a single symbol and generate the full 14-point institutional analysis:

cmd

python quickscan.py "Volatility 75 (1s) Index"
cmd

python quickscan.py EURUSD
B. Multi-Symbol Scan
Scan multiple symbols sequentially. If multiple symbols are scanned, an executive Master Summary Table is printed at the end:

cmd

python quickscan.py "Volatility 75 (1s) Index" "Volatility 25 Index" EURUSD
C. Continuous Scanning Loop (Interval Mode)
To automatically re-scan symbols on a recurring loop, append an interval string (10s, 30s, 1m, 5m) as the last argument:

cmd

python quickscan.py "Volatility 75 (1s) Index" 30s
cmd

python quickscan.py "Volatility 75 (1s) Index" "Volatility 25 Index" 1m
Press Ctrl + C at any time to stop the loop.

D. Customizing Risk % and ATR Stop Multiple
--risk <FLOAT>: Set risk percentage per trade based on account equity (default: 5.0%).
--stop-atr <FLOAT>: Set stop loss distance multiplier for ATR fallback (default: 2.0).
cmd

python quickscan.py "Volatility 75 (1s) Index" --risk 2.5 --stop-atr 1.5
E. Compact Compare Mode (--compare)
Prints a streamlined, side-by-side comparison table of all watched symbols instead of detailed individual panels:

cmd

python quickscan.py "Volatility 75 (1s) Index" "Volatility 25 Index" EURUSD --compare
4. Understanding Output Sections
Every detailed scan output is organized into 14 institutional analysis sections:

Section	Description
1. Trade Decision Layer	Direct trade signal (BUY NOW, SELL NOW, WAIT FOR PULLBACK, NO TRADE) and rationale.
2. Entry Quality Score	0–100 weighted score, setup Grade (A+, A, B, C), and confidence level.
3. Pullback & State	Precise trend structure classification (e.g., Deep Pullback into Discount).
4. Actionable Instructions	Exact Buy/Sell entry zones, required confirmations, and expected R:R ratio.
5. Chart Marking Assistant	Coordinates and levels to draw on your MT5 chart (Swing High/Low, ORB, VWAP, Pivots, FVGs).
6. Entry Zone Generator	Calculated price ranges for optimal limit or market orders.
7. Dynamic Stop Loss	Chosen stop price based on structural swing, ATR, or Order Block boundaries.
8. Multiple Profit Targets	TP1 (Conservative), TP2 (Structural), and TP3 (Extended Runner) with hit probabilities.
9. Trade Invalidation	Exact condition that invalidates the trade setup (e.g., Close below M5 Swing Low).
10. Institutional Checklist	8-point checklist status (PASS, FAIL, WARN) evaluating EMAs, RSI, VWAP, ORB, and ADX.
11. Position Sizing	Account-fitted lot size calculation matching your --risk % parameter.
12. Market Structure	ADX trend strength, market phase (Expansion vs Compression), and liquidity location.
13. Executive Summary	Concise setup summary card for rapid trade execution.
14. Visualization Guidance	Guidelines for chart drawing and manual order management.
5. Troubleshooting
MT5 init failed: Make sure MetaTrader 5 desktop application is open and logged into your trading account before running the script.
NOT AVAILABLE on this account: Verify the symbol name matches your broker's exact symbol name in MT5 Market Watch window.
No color formatting: Windows Terminal, PowerShell, or Command Prompt support ANSI colors natively. If using legacy cmd.exe, enable color mode or run inside Windows Terminal.
