# Research findings

Measured on 2026-08-03 against roughly 69 days of M5 history (20,000 candles
per symbol, about 1,000 setups each) using `reclaim_test.py`.

The setup tested is the one the scanner trades: buy a pullback to the M5
EMA20 zone (EMA20 +/- 0.2 ATR) while EMA20 > EMA50, stop 2 ATR below entry,
targets at 1.5 / 2.5 / 4.0 ATR, resolved by whichever level price reaches
first. A bar touching both stop and target is scored a stop.

## Spread decides profitability, not signal quality

Gross expectancy is positive on 19 of 20 volatility indices, but only
+0.005R to +0.084R. Spread costs 0.032R to 0.047R per trade on most of
them, so it consumes most or all of the edge. After spread, 8 of 20 remain
positive.

| Symbol | Gross | Spread | Net |
| --- | ---: | ---: | ---: |
| Volatility 15 Index | +0.084 | 0.034 | **+0.050** |
| Volatility 25 Index | +0.075 | 0.033 | **+0.042** |
| Volatility 15 (1s) Index | +0.067 | 0.034 | **+0.033** |
| Volatility 10 (1s) Index | +0.059 | 0.032 | **+0.027** |
| Volatility 5 Index | +0.045 | 0.034 | +0.011 |
| Volatility 30 Index | +0.043 | 0.032 | +0.011 |
| Volatility 5 (1s) Index | +0.023 | 0.033 | -0.010 |
| Volatility 30 (1s) Index | +0.010 | 0.032 | -0.022 |
| Volatility 75 (1s) Index | +0.005 | 0.041 | **-0.036** |
| Volatility 250 (1s) Index | +0.026 | 0.377 | -0.351 |

Volatility 75 (1s) pays eight times more in spread than its gross edge: it
loses money before signal quality enters into it, which matches its live
record (worst performer of the 2026-08-03 demo session, -$281.96 over two
trades). Volatility 250 (1s) is untradeable with this strategy at any
signal quality.

## Two entry ideas that did not survive testing

**Second touch of the zone.** The premise was that a first touch often
fails and the retest holds. Across four synthetics and four real markets
the result was inconsistent: two favoured the second touch, one the first,
the rest a wash, with up-rates averaging about 51%.

**Waiting for price to reclaim the zone.** Improved expectancy slightly on
EURUSD and GBPUSD (about +0.07R), was clearly worse on XAUUSD, and made no
difference on synthetics, while cutting trade count 35-40%. Price crosses
the zone boundary 1.6 times on average before reclaiming, so the chop is
mild, but the rule is not worth its cost.

Neither was implemented.

## Method notes, including two mistakes worth not repeating

Forward return over a fixed horizon is the wrong measure for a
stop-and-target strategy. It was tried first and pointed the wrong way: a
rule can leave price no higher while still holding its stop far more often,
which is invisible to a forward-return test but decisive in trading. Every
conclusion here comes from resolving trades against real stop and target
levels instead.

Sample size changed the answer outright. A 5,000-candle run (about 130
setups per symbol) suggested four of five instruments were unprofitable and
Volatility 10 was uniquely good. At 20,000 candles that reversed: 19 of 20
are positive gross, and Volatility 10 is ordinary, beaten by Volatility 15
and 25. The earlier result was noise read as signal.

Slippage is not modelled, only spread, so the marginal entries here
(Volatility 100 Index at +0.004, Volatility 50 Index at +0.001) are
effectively zero. About 69 days is a limited record.
