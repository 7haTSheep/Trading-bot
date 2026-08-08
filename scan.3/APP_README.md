# QuickScan

QuickScan watches the charts in MetaTrader 5 and tells you what it thinks
about each one: whether there is a trade worth taking, where you would get in,
where you would get out if it went wrong, and where you would take profit.

It can also draw all of that onto your MT5 charts, and keep a record of the
trades you actually took.

**It is a tool for thinking, not a money machine.** Please read
[Before you trade real money](#before-you-trade-real-money) at the bottom. It
is short and it is the most important part of this file.

---

## What you need

- A Windows PC (64-bit)
- MetaTrader 5, installed and logged into your account
- About ten minutes

You do **not** need Python, and you do not need to know how to program.
Everything QuickScan needs is already inside this folder.

---

## Setting it up

### 1. Keep the whole folder together

QuickScan is the folder, not just the file. `QuickScan.exe` will not start
without the `_internal` folder sitting next to it. Copy or move the **whole
QuickScan folder**, never the single file.

### 2. Run Setup

Double-click **`Setup.bat`**.

It checks that MetaTrader 5 is installed, offers to download it if not, and
copies the chart files into it. It asks before installing anything and it is
safe to run more than once.

### 3. Compile the chart files

Setup cannot do this for you, and QuickScan cannot draw on your charts until
it is done. It takes about thirty seconds.

1. Open MetaTrader 5 and press **F4**. A second program called MetaEditor opens.
2. On the left you will see **QuickScanChart**, **QuickScanEA** and
   **QuickScanLauncher**.
3. Click each one and press **F7**.

"Compile" just means turning the file into something MetaTrader can run. You
only ever do this once.

### 4. Turn the chart drawing on

**This is the step people miss, and without it your charts stay blank.**

1. In MetaTrader press **Ctrl+N** to open the Navigator panel.
2. Find **QuickScanLauncher** under **Expert Advisors**.
3. Drag it onto any one chart — it does not matter which.
4. Tick **Allow Algo Trading** in the box that appears.
5. Check the **Algo Trading** button in the toolbar at the top is green.

You do this once. From then on, whenever QuickScan scans a symbol, the
launcher opens a chart for it and draws the levels on automatically.

---

## Using it

Start **`QuickScan.exe`**. MetaTrader 5 must already be open and logged in.

### The Scan tab

1. Press **Load symbols from MetaTrader**
2. Tick the symbols you want to watch (type in the filter box to find them)
3. Press **Start scanning**

Reports appear on the right. If you leave **Keep scanning as each candle
closes** ticked, it re-checks every time a candle finishes and adds a fresh
report.

Scan **two or more symbols** and you also get a summary table at the end,
comparing them best score first. With a single symbol there is nothing to
compare it against, so the table is skipped.

Two settings are worth knowing:

| Setting | What it does |
|---|---|
| **Risk per trade** | How much of your account a trade would risk, as a percentage. Only affects the position size the report *suggests*. |
| **Stop distance (ATR)** | How far the stop-loss sits, measured in average candle sizes. Bigger means more room and a smaller position. |

### The Trades tab

This is the record of what you actually did, read straight from MetaTrader —
there is nothing to import or export.

- **Net profit, win rate, expectancy, average R, worst losing run**
- **Equity curve** — your running total, trade by trade. Above the dashed line
  means the account grew.
- **Full history table** — every closed trade with entry, exit, stop and profit

**Expectancy** is the one to watch. It is what an average trade made or lost.
If it is negative, repeating what you have been doing loses money, however
good any single trade looked.

The **R** column needs a stop-loss to have been on the order. Trades placed
without one show `--`.

### The pre-trade checklist

On the right of the Trades tab. Five questions to answer honestly before you
enter. Nothing unlocks until all five are ticked, and pressing **Log checklist
and reset** keeps a record.

It is there because most of what goes wrong is decided *before* the trade —
oversizing, no stop, trading to win back a loss. None of that can be spotted
in a profit column afterwards.

### Light and dark

The box in the top right switches between **System**, **Light** and **Dark**.
System follows whatever Windows is set to. Your choice is remembered.

---

## Reading a report

The most important line is the **decision**:

| It says | It means |
|---|---|
| **BUY NOW** | Conditions for buying are met right now |
| **SELL NOW** | Conditions for selling are met right now |
| **WAIT FOR PULLBACK** | Right idea, wrong price. Price has run too far; wait for it to come back |
| **WAIT FOR CONFIRMATION** | Nearly there, but something has not lined up yet |
| **NO TRADE** | Nothing worth taking |

Then a **score** out of 100 and a **grade** (A+, A, B, C, Wait).

Treat the score as "how many boxes were ticked", not "how likely this is to
win". Whether a high score actually wins more often is a separate question,
and one this tool measures rather than assumes — see below.

You also get the entry zone, stop loss, three profit targets, and what would
have to happen for the idea to be dead.

### R:R, briefly

Numbers like `1.59:1` are reward against risk: if the stop costs you £100,
hitting that target makes £159.

Anything below `1:1` means you are risking more than you stand to gain, and
you would need to be right more than half the time just to break even. Worth
checking before you take the trade.

---

## Where your data is kept

Everything QuickScan records lives here:

```
C:\Users\<your name>\AppData\Local\QuickScan
```

Deliberately **not** in this folder — updating QuickScan replaces this folder,
and your history would vanish without you noticing.

| File | What it is |
|---|---|
| `signals.jsonl` | Every signal given, and how it later turned out |
| `discipline.jsonl` | Your logged checklists |

Moving to a new PC? Copy that folder across by hand. It does not travel with
the application.

---

## Does any of this work?

This is the honest part.

QuickScan measures itself. Every signal is recorded and later checked against
what price actually did, so its claims can be tested rather than believed.

What that measurement says so far, across roughly 11,000 recorded setups:

- The edge is **small**. Most symbols come out close to break-even once the
  spread is accounted for.
- **The spread matters more than the strategy.** The cost of entering is often
  larger than the whole expected gain. On Volatility 75 the spread costs
  several times more than the edge it is trying to capture, so that symbol
  loses money almost regardless of how good the signals are.
- **A high score has not been shown to beat a low one.** There is not enough
  live data to say, and QuickScan will not pretend otherwise.

When a symbol has lost money consistently *and* there is enough evidence to be
confident about it, the report says so directly. Until then it says the
evidence is inconclusive rather than guessing.

---

## Letting it trade for you

**QuickScanEA** can place trades automatically. It is separate from this
window, it is off unless you deliberately attach it in MetaTrader, and
QuickScan.exe never places a trade itself.

It will not touch a real-money account unless you change a setting called
`AllowLiveAccount`. Leave that alone. Use a demo account.

**Check `RiskPercent` before you start it.** Setting it too high once cost a
demo account half its value in five trades, because every trade was sized at
the largest the broker would allow. It now refuses trades that big instead of
placing them, but the setting is still yours to get right.

---

## When something does not work

**"The charts are blank"** — QuickScanLauncher is not attached. Go back to
step 4 above. This is by far the most common cause.

**"QuickScan.exe won't start"** — the `_internal` folder is missing. Copy the
whole folder across, not just the .exe.

**"Could not reach MetaTrader 5"** — MetaTrader is not running, or not logged
in. Open it first, then press Start again.

**"NOT AVAILABLE on this account"** — your broker spells that symbol
differently. Open Market Watch in MT5 and copy the name exactly, including
spaces and brackets.

**"cannot load QuickScanChart"** — it has not been compiled. F4, click it, F7.

**The Trades tab is empty** — you have no closed trades in the chosen period.
Try a longer one from the dropdown. Trades still open do not appear; only
closed ones can be scored.

---

## Before you trade real money

Please take this seriously.

**This is not advice.** It is software that applies rules to price. It cannot
know what will happen next, and neither can anyone else.

**The measured edge is very small, and may be nothing at all.** The section
above is not modesty; it is what the data says.

**Deriv's Volatility indices are not real markets.** They are generated
numbers designed to move like markets. There are no companies, no news and no
other traders behind them.

**Automated trading fails in ways manual trading does not.** It can repeat a
mistake hundreds of times without pausing. One wrong setting emptied half a
demo account in five trades, and it did it in minutes.

**Use a demo account until you have your own evidence.** Not until it feels
right, and not until it has a good day — until the numbers, over enough
trades, say something.

Never risk money you cannot afford to lose.

---

## Credits

QuickScan bundles two open-source typefaces, both under the SIL Open Font
License. The licence texts are in `_internal\assets\fonts`.

- **Syne** — Bonjour Monde and Lucas Descroix
- **JetBrains Mono** — JetBrains
