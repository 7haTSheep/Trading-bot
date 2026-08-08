# Changelog

Notable changes to QuickScan. Newest first.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The **Fixed** entries are worth reading even if the rest is skimmed. Several
were bugs that made the tool quietly report things that were not true, which
is worse than crashing, and knowing which numbers were affected matters if you
acted on them.

---

## [1.0.0] — 2026-08-08

First released build. QuickScan now ships as a Windows application that needs
no Python installed.

### Added

- **QuickScan.exe** — a windowed application. Pick symbols, set risk, press
  Start. Same scanning code as the command line, so the two cannot disagree.
- **Trades tab** — closed positions read straight from MetaTrader, with net
  profit, win rate, expectancy, average R, worst losing run and an equity
  curve. No export or import step.
- **Pre-trade checklist** — five questions before entry, logged when
  completed. Carried over from the trade discipline app.
- **Light, Dark and System themes**, remembered between runs.
- **Update checking** — asks GitHub whether a newer release exists and offers
  to open the download page. Nothing installs itself. Switchable off, and it
  never interrupts if the check fails.
- **QuickScanLauncher** — attach it once in MetaTrader and it opens a chart
  for every symbol scanned and draws the levels on automatically.
- **Setup.bat** inside the application folder: finds or installs MetaTrader 5
  and copies the chart files in.
- **Calibration** — per-symbol verdicts gated on 200 resolved trades and a
  mean clear of zero by 1.96 standard errors, so a good week cannot be
  mistaken for an edge.
- **Entry placement tracking** — whether each entry landed in the published
  zone, before price reached it, or after price passed it.
- **Automatic outcome resolution** during a running scan, every 12 candles.

### Changed

- **Signal and checklist logs moved to `%LOCALAPPDATA%\QuickScan`.** They used
  to sit beside the program, which in a packaged application means inside the
  folder every update replaces — ten thousand recorded signals were one
  reinstall away from being deleted silently. Existing logs migrate on first
  run: copied, size-checked, and the original left renamed rather than
  deleted.
- **Redesigned** around a retro-futurist instrument look: warm near-black
  under grain, amber as the only interactive colour, green and crimson
  reserved for direction and outcome so a coloured number always means
  something.
- **Syne and JetBrains Mono are bundled**, so the window renders identically
  on a machine with neither installed. Both OFL; licences ship alongside.
- **The application's README** replaced the source project's, which told the
  reader to run `Install.bat` and `python quickscan.py` — neither exists next
  to the executable.
- **Reports no longer word-wrap.** Wrapping pushed the tail of a long line to
  column zero and the columns stopped lining up.

### Fixed

- **The master summary never appeared in the application.** `scan_symbol`
  collects its rows through an argument the window was not passing, so the
  comparison table shown after a multi-symbol command-line scan was simply
  absent from the app.
- **Outcome resolution never worked, and every signal was recorded as
  EXPIRED.** Bars were fetched with `copy_rates_from`, which returns the bars
  *ending* at a time rather than following it, so resolution looked at price
  before the signal. Every outcome recorded before this is meaningless; the
  history was rebuilt afterwards.
- **QuickScanEA silently traded at the broker's maximum lot size** when the
  requested risk exceeded it, instead of refusing. One misconfigured run cost
  a demo account half its value in five trades. It now declines the trade and
  says why.
- **TP2 could be placed beyond TP3.** A pivot level was snapped to
  unconditionally rather than only when it fell between the neighbouring
  targets. The test that should have caught it used a fixture where TP2 and
  TP3 were equal.
- **A trailing space in a symbol name silently dropped that symbol** from the
  scan. Twice.
- **The re-entry pullback filter did nothing.** It waited for 0.5 ATR, but ATR
  *is* roughly the average candle range, so the condition was satisfied within
  a single candle.
- **Chart markings accumulated to hundreds of stale objects**, because the
  de-duplication list lived in memory and reset whenever the indicator
  reloaded.
- **Stop modifications spammed error 10025** — prices were compared without
  normalising to the symbol's digits first.
- Build failures from `PermissionError` on Windows: PyInstaller now stages its
  output and copies over the top, so an open Explorer window or a running copy
  of the app cannot stop a rebuild.

### Known limitations

- **Windows only.** MetaTrader 5's Python interface is a Windows library, and
  the application is a Windows executable. See the README.
- **The measured edge is small and may be nothing.** Across roughly 11,000
  recorded setups most symbols sit near break-even once spread is charged, and
  on Volatility 75 the spread costs several times the edge being chased.
- **A high score has not been shown to beat a low one.** There is not yet
  enough live data to say either way, and the tool reports that rather than
  guessing.
- **`MetaTrader5` indicators cannot use `WebRequest` on this build**
  (`error 4014`), so the scanner passes levels to the chart through files
  rather than HTTP.

[1.0.0]: https://github.com/7haTSheep/Trading-bot/releases/tag/v1.0.0
