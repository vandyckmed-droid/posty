# Momentum 100

An interactive cross-sectional equity momentum screen with an inverse-volatility
watchlist builder, backed by Financial Modeling Prep end-of-day data.

## Pipeline

```
U.S. common stocks  →  top 1,000 by 63-day ADDV  →  12-1 + 6-1 percentile blend
                    →  top 100 displayed  →  watchlist  →  126-day inverse-vol weights
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
eight minutes.

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

| Path                        | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `scripts/build_data.py`     | FMP fetch, screening, momentum and volatility     |
| `scripts/build_artifact.py` | Inlines the dataset into the template             |
| `artifact/template.html`    | Interface source, with a `__DATA__` placeholder   |
| `artifact/index.html`       | Generated, publishable artifact                   |
| `data/momentum.json`        | Generated dataset (top 100 rows plus run metadata)|

Research and educational use only — mechanical outputs of the formulas above,
not investment advice.
