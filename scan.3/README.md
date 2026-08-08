# QuickScan

QuickScan watches the charts in MetaTrader 5 for you and tells you what it
thinks about each one: whether there is a trade worth taking, where you would
get in, where you would get out if it went wrong, and where you would take
profit.

It can also draw all of that straight onto your MT5 chart, and it can place
the trades itself if you let it.

**It is a tool for thinking, not a money machine.** Please read
[Before you trade real money](#before-you-trade-real-money) at the bottom.
That section is short and it is the most important part of this file.

---

## What you need

- A Windows PC
- MetaTrader 5, installed and logged into your account
- About ten minutes

You do **not** need to know how to program.

---

## Setting it up

Double-click **`Install.bat`**.

It checks whether you have everything, offers to download anything missing
(Python, MetaTrader 5), and copies the chart files into MetaTrader for you.
It asks before installing anything, and it is safe to run more than once.

When it finishes it will tell you to do one thing by hand, because it cannot
do it for you:

1. Open **MetaEditor** (press **F4** inside MetaTrader)
2. Find **QuickScanChart** and **QuickScanEA** in the list on the left
3. Click each one and press **F7** to compile it

Compiling just means "turn this into something MetaTrader can run". You only
do it once.

---

## Running your first scan

Open a **Command Prompt** in this folder (in File Explorer, click the address
bar, type `cmd`, press Enter), then type:

```
python quickscan.py "Volatility 75 (1s) Index"
```

That scans one symbol once and prints a report.

**Put quotes around any name with spaces in it.** `"Volatility 75 (1s) Index"`
needs them; `EURUSD` does not.

### Keeping it running

Add a timeframe at the end and it keeps going, re-checking each time a new
candle finishes:

```
python quickscan.py "Volatility 75 (1s) Index" 5m
```

`5m` means it re-checks every time a 5-minute candle closes. You can use
`1m`, `5m`, `15m`, `30m`, `1h`, `4h` or `1d`. Press **Ctrl+C** to stop.

### Several symbols at once

Just list them:

```
python quickscan.py "Volatility 15 Index" "Volatility 25 Index" EURUSD 5m
```

At the end you get a summary table comparing them, best score first.

### Two settings worth knowing

| Setting | What it does |
|---|---|
| `--risk 1` | How much of your account a trade would risk, as a percentage. Only affects the position size it *suggests*. |
| `--stop-atr 2.0` | How far away the stop-loss goes, measured in average candle sizes. Bigger means more room, and a smaller position. |

```
python quickscan.py "Volatility 15 Index" --risk 1 --stop-atr 2.0 5m
```

---

## Reading the report

The most important line is the **decision**:

| It says | It means |
|---|---|
| **BUY NOW** | Conditions for buying are met right now |
| **SELL NOW** | Conditions for selling are met right now |
| **WAIT FOR PULLBACK** | Right idea, wrong price. Price has run too far; wait for it to come back |
| **WAIT FOR CONFIRMATION** | Nearly there, but something has not lined up yet |
| **NO TRADE** | Nothing worth taking |

Then the **score**, from 0 to 100, and a **grade** (A+, A, B, C, Wait). Higher
means more of its checks agreed.

Treat the score as "how many boxes were ticked", not "how likely this is to
win". Whether a high score actually wins more often is a separate question,
and one this project measures rather than assumes. See
[Does any of this work?](#does-any-of-this-work) below.

You also get:

- **Entry zone** — the price range it would want to buy or sell in
- **Stop loss** — where the idea is proven wrong, so you get out
- **TP1, TP2, TP3** — profit targets, nearest first
- **Invalidation** — what would have to happen for the idea to be dead

### R:R, briefly

You will see numbers like `1.59:1`. That is reward against risk: if the stop
costs you £100, hitting that target makes £159.

Anything below `1:1` means you are risking more than you stand to gain, and
you would need to be right more than half the time just to break even. It is
worth checking.

---

## Seeing it on the chart

Two extra pieces put the same information onto your MT5 charts.

**QuickScanChart** is the drawing. Attach it to a chart and you get the entry
zone as a shaded box, the stop and targets as lines, all labelled, plus a
small panel showing the decision, grade and score.

**QuickScanLauncher** saves you doing that by hand. Attach it once to any
chart and it opens a chart for every symbol you scan and adds the drawing to
each. To use it: find it under **Expert Advisors** in the Navigator panel,
drag it onto any chart, tick **Allow Algo Trading**, and make sure the
**Algo Trading** button in the toolbar is green.

You need the scanner running for either to show anything: the scanner works
out the numbers, and these only draw them.

---

## Letting it trade for you

**QuickScanEA** places trades from the signals automatically.

Before you even consider this, read the last section of this file.

It will not touch a real-money account unless you deliberately change a
setting called `AllowLiveAccount`. Leave that alone. Use a demo account.

Settings that matter, all editable when you attach it:

| Setting | Default | What it does |
|---|---|---|
| `RiskPercent` | 1.0 | Percentage of the account risked per trade |
| `MaxRiskPerTradePct` | 5.0 | Hard ceiling. A trade wanting more is refused outright |
| `MaxDailyLossPct` | 3.0 | Stops trading for the day after losing this much |
| `MaxOpenPositions` | 3 | Most trades open at once |
| `MinGradeScore` | 80 | Ignores setups scoring below this |
| `AllowLiveAccount` | false | Must be true to trade real money. Leave it false |

**Check `RiskPercent` before you start it.** Setting it too high once cost a
demo account half its value in five trades: every trade was sized at the
largest the broker would allow. The EA now refuses trades that big instead of
placing them, but the setting is still yours to get right.

Once in a trade it moves your stop-loss as things go your way: first to
slightly above your entry, so the trade can no longer lose, then up to each
profit target as price passes it.

---

## Does any of this work?

This is the honest part.

The project measures itself. Every signal is recorded, and later checked
against what price actually did, so its claims can be tested rather than
believed.

What that measurement says so far:

- The edge is **small**. Across roughly 11,000 historical setups, most symbols
  came out close to break-even once the spread was accounted for.
- **The spread matters more than the strategy.** The cost of entering a trade
  is often larger than the whole expected gain. On Volatility 75 the spread
  costs several times more than the edge it is trying to capture, so that
  symbol loses money almost regardless of how good the signals are.
- **A high score has not yet been shown to beat a low one.** There is not
  enough live data to say, and the project will not pretend otherwise.

You can look at this yourself at any time:

```
python outcomes.py          how past signals actually turned out
python calibration.py       which symbols are worth trading, if any
python entry_accuracy.py    whether entries hit the zone, or came too early
```

If a symbol is losing money consistently and there is enough evidence to be
sure, the scanner starts warning you about it. Until it is sure, it says so
rather than guessing.

---

## Other bits

```
python dashboard.py         a live screen you can leave open beside MT5
```

`research/FINDINGS.md` has the detail behind the numbers above, including two
ideas that sounded good and were tested and dropped.

---

## When something does not work

**"python is not recognised"** — Python is not installed, or not set up so
Windows can find it. Run `Install.bat` again and let it install Python.

**"MT5 init failed"** — MetaTrader 5 is not running, or not logged in. Open it
first.

**"NOT AVAILABLE on this account"** — your broker spells that symbol
differently. Open the Market Watch window in MT5 and copy the name exactly.

**Odd characters or a crash when printing** — type this first, then run again:
```
set PYTHONIOENCODING=utf-8
```

**The chart shows nothing** — the scanner needs to be running, and it must be
scanning that exact symbol.

**"cannot load QuickScanChart"** — it has not been compiled. F4, select it,
F7.

---

## Before you trade real money

Please take this seriously.

**This is not advice.** It is software that applies rules to price. It cannot
know what will happen next, and neither can anyone else.

**The measured edge is very small, and may be nothing at all.** The section
above is not modesty; it is what the data says.

**Deriv's Volatility indices are not real markets.** They are generated
numbers designed to move like markets. There are no companies, no news, and
no other traders behind them.

**Automated trading fails in ways manual trading does not.** It can repeat a
mistake hundreds of times without pausing. One wrong setting emptied half a
demo account in five trades, and it did that in minutes.

**Use a demo account until you have your own evidence.** Not until it feels
right, and not until it has a good day. Until the numbers, over enough
trades, say something.

Never risk money you cannot afford to lose.
