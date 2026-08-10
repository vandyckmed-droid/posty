# Momentum 100

An interactive cross-sectional equity momentum screen with an inverse-volatility
watchlist builder, backed by Financial Modeling Prep end-of-day data.

## Pipeline

```
U.S. common stocks  →  top 1,000 by 63-day ADDV  →  12-1 + 6-1 percentile blend
                    →  raw or risk-adjusted basis   →  top 100 displayed
                    →  watchlist  →  126-day inverse-vol weights
                    →  sector counts and sector weight exposure
```

**Universe.** Actively-traded common stocks on NYSE, NASDAQ and NYSE American.
ETFs and funds are excluded by the screener; ADRs are excluded on the issuer
profile; preferred shares, warrants, rights and units are excluded by symbol
convention. Class shares such as `BRK-B` are kept — they are common stock.

**Liquidity.** 63-trading-day average daily dollar volume,
`ADDV = mean(close × volume)`. The 1,000 most liquid eligible names form the
ranking universe. Dollar volume is traded notional, so ADDV is the one figure
computed from unadjusted closes; everything else uses adjusted prices.

**Momentum.** Every return is a total return, taken from FMP's
`historical-price-eod/dividend-adjusted` closes. This matters: over two years the
gap between total and price-only return reaches 7–9pp for dividend payers
(KO +35.6% vs +28.1%), which would otherwise bias the ranking against them.

`12-1` is the return from 252 trading days ago to 21 trading days ago; `6-1` runs
from 126 trading days ago to the same endpoint. Skipping the most recent month
avoids short-term reversal. Each is percentile-ranked within the 1,000-name
universe and blended:

```
Combined Momentum Score = 0.5 × P(12-1) + 0.5 × P(6-1)
```

## Ranking bases

The screen ranks on either of two bases, switchable in the UI.

**Raw** uses the returns above directly.

**Risk-adjusted** divides each leg by the standard deviation measured over that
leg's *own* window. Both σ windows end where the return ends — a month back, not
at the last session — so numerator and denominator span exactly the same days:

```
IR(12-1) = ln(1 + R12-1) / (σ₂₅₂ × √252)      252 daily log returns ending at t-21
IR(6-1)  = ln(1 + R6-1)  / (σ₁₂₆ × √126)      126 daily log returns ending at t-21
```

Log returns because a cumulative log return over N days has standard deviation
`σ√N`, which makes the ratio a genuine t-statistic of drift rather than an
arithmetic quantity that rewards multi-baggers for their arithmetic. The
simple-return variant disagrees by a mean of 8.9 and up to 35 rank places.

Both bases percentile-rank and blend identically within the same 1,000-name
universe, so only the inputs differ. Inverse-volatility weighting is untouched —
it still uses the 126-day realized volatility ending at the last session.

The two bases share only 56 of their top 100. Risk adjustment does what it says:
median realized volatility of the displayed names falls from 82.5% to 51.1% and
the maximum from 702% to 178%, as volatility-driven names (ASTC, RXT, AAOI) drop
out and steady compounders (CAT, CSCO, PANW, MOG-A) come in. The build ships the
union of both top-100s so either view is complete client-side.

**Volatility and weights.** Realized volatility is the sample standard deviation
of the last 126 daily returns, annualized by `√252`. Watchlist weights are
inverse-volatility, normalized to 100%:

```
w_i = (1 / σ_i) / Σ(1 / σ_j)
```

Weights are held at full precision and rounded for display with a
largest-remainder pass, so the shown figures always total exactly 100.0%.

## Build

```bash
export API_KEY=<your FMP key>
python3 scripts/build_data.py       # fetch + compute  -> data/momentum.json
python3 scripts/build_artifact.py   # inline the data  -> artifact/index.html
```

`build_data.py` screens roughly 4,500 candidates and pulls ~16 months of daily
bars for each, then re-fetches the liquid head as two years of dividend-adjusted
closes for the returns, volatility and detail charts. A full run takes about
thirteen minutes.

## Interface

Phone-first. The app is a single column sized for a handset and centred on wider
screens — deliberately a phone app rather than a layout that reflows into a
dashboard.

Three tabs sit in a thumb-reachable bottom bar:

- **Ranks** — a scannable card list, one metric per row (12-1 by default, or
  whatever the list is sorted by, so the active sort is always legible). Search
  scrolls away; the basis / sort / sector rail stays pinned.
- **Watchlist** — portfolio summary, holdings with inverse-volatility weights,
  and sector exposure.
- **Method** — formulas, data provenance and freshness.

Sort and sector choosers, ticker detail and the compare picker are all bottom
sheets: they arrive under the thumb and dismiss with a downward swipe. Every
control clears a 36px touch target, and safe-area insets are respected top and
bottom.

## Detail and comparison view

Tapping a ticker opens a detail sheet — a normalized cumulative total-return
chart, `R(t) = Adjusted(t) / Adjusted(start) - 1`, rebased to 0% at the start of
the selected window (3M / 6M / 1Y / 2Y, default 1Y). Above it sit only the
momentum rank, 12-1, 6-1 and 126-day volatility.

Compare puts up to four stocks on one chart, each rebased to 0% at the same
window start so relative performance reads directly. Dragging across the chart
moves a crosshair that reports the date and every displayed stock's cumulative
return at that session. No candlesticks, volume or technical overlays — the
chart answers one question.

Chart history ships as integer ratios (×10000) against each series' first
observation on a shared trading calendar, so `R` is exact for any window and the
payload stays small.

The key is read from the environment by the build step only. `artifact/index.html`
is fully self-contained — it ships the computed dataset and nothing else, with no
API calls, no credentials and no raw API responses in the client. The watchlist
persists to `localStorage` in the viewer's browser.

## Layout

The artifact must ship as one self-contained file, but the source is modular.
`build_artifact.py` concatenates `src/styles/*.css` and `src/app/*.js` in
filename order (the numeric prefixes are the dependency order), wraps the app in
a single IIFE, inlines the dataset and writes `artifact/index.html`. Editing a
view means editing one small file, not a 1,400-line template.

| Path                        | Purpose                                             |
| --------------------------- | --------------------------------------------------- |
| `scripts/build_data.py`     | FMP fetch, screening, momentum and volatility        |
| `scripts/build_artifact.py` | Bundles `src/` + dataset into the artifact           |
| `src/shell.html`            | Page shell and tab bar                               |
| `src/styles/`               | Tokens, base, shell, ranks, watchlist, sheet         |
| `src/app/01-format.js`      | Number and date formatting                           |
| `src/app/02-calc.js`        | Weights, sector exposure, rebasing, axis maths       |
| `src/app/03-store.js`       | Dataset access, UI state, persistence, notification  |
| `src/app/04-chart.js`       | Canvas chart, crosshair geometry, sparklines         |
| `src/app/05-sheet.js`       | Bottom-sheet host: swipe, focus, scroll lock         |
| `src/app/06-08-view-*.js`   | Ranks, Watchlist, Method screens                     |
| `src/app/09-view-detail.js` | Ticker detail and compare                            |
| `src/app/10-pickers.js`     | Sort and sector choosers                             |
| `src/app/11-main.js`        | Tab navigation and one delegated click handler       |
| `artifact/index.html`       | Generated, publishable artifact                      |
| `data/momentum.json`        | Generated dataset (both bases' top 100, plus metadata)|

The layers are separable on purpose: calculations are pure and DOM-free, the
store is the only thing that touches `DATA` or `localStorage`, and views render
from the store without reaching past it. Changing the ranking maths, adding a
card, or adding a tab each touch one layer.

Research and educational use only — mechanical outputs of the formulas above,
not investment advice.
