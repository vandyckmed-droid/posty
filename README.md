# Momentum 100

An interactive cross-sectional equity momentum screen with an inverse-volatility
watchlist builder, backed by Financial Modeling Prep end-of-day data.

## Pipeline

```
U.S. common stocks  →  top 500 by 63-day ADDV  →  12-1 + 6-1 percentile blend
                    →  top 100 displayed  →  watchlist  →  126-day inverse-vol weights
                    →  sector counts and sector weight exposure
```

**Universe.** Actively-traded common stocks on NYSE, NASDAQ and NYSE American.
ETFs and funds are excluded by the screener; ADRs are excluded on the issuer
profile; preferred shares, warrants, rights and units are excluded by symbol
convention. Class shares such as `BRK-B` are kept — they are common stock.

**Liquidity.** 63-trading-day average daily dollar volume,
`ADDV = mean(close × volume)`. The 500 most liquid eligible names form the
ranking universe.

**Momentum.** `12-1` is the return from 252 trading days ago to 21 trading days
ago; `6-1` runs from 126 trading days ago to the same endpoint. Skipping the most
recent month avoids short-term reversal. Each is percentile-ranked within the
500-name universe and blended:

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
bars for each; a full run takes about six minutes.

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
