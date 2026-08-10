# posty

A risk-adjusted momentum screen over every liquid US-listed ETF, built for a phone
screen. It ranks funds by return per unit of volatility, folds near-identical funds
together so the list shows *bets* rather than tickers, and reports how many
independent bets the top of the list actually contains.

The output is a single self-contained HTML page with all data embedded — no network
access at runtime, no backend.

## The score

For each fund, over a **formation window** that stops 21 trading sessions short of
today (the "−1", which sidesteps short-term reversal):

1. Daily log returns `r_t = ln(P_t / P_t−1)` on **split- and dividend-adjusted** closes
2. Annualized return = `sum(r) × 252/n`
3. Annualized volatility = `stdev(r) × √252`
4. **Score = (2) ÷ (3)**

Two windows, ranked over the same universe so they stay directly comparable:

| window | lookback | returns | reads as |
| --- | --- | --- | --- |
| **6−1** | `t−126 … t−21` | 105 | fresher trends, noisier estimate (default) |
| **12−1** | `t−252 … t−21` | 231 | the classic academic window, slower to turn |

No risk-free rate is subtracted, so this is a raw return/volatility ratio rather than
a Sharpe ratio. An **excess score** — the same figure net of the T-bill return over
the same window, taken from BIL's own return — is computed alongside it and available
as a sort.

## Universe

Starting from the vendor's full ETF list, the screen keeps plain US-listed tickers
that clear one baseline liquidity bar:

- **median daily dollar volume ≥ $5M** over the last 63 sessions — median, not mean,
  so a single block trade cannot lift a thin fund through the gate
- **last close ≥ $5**
- **≥ 273 sessions of history**, so the longest formation window exists

Delisted tickers that still quote a stale last price drop out automatically: they
return no price history. As of the last build, 10,404 listed ETFs → 6,284 US-listed
→ 2,092 pre-screened → **1,058 ranked**.

## Grouping and diversification

Funds whose daily returns correlate above a threshold (0.95 by default, 0.90
available) with a better-ranked fund are folded into that fund's row. Membership is
measured **against the representative**, never chained transitively, so a group
cannot drift into a different bet. Correlations are recomputed per window.

The readout reports `N² / ΣΣ|r_ij|` over the top rows shown — the number of unrelated
holdings carrying the same risk as that basket. Absolute values matter: an inverse
fund is a perfect hedge against its own long, which is one bet expressed twice, not
free diversification.

Two findings this surfaced, both documented in the page's own method section:

- SOXX, SOXQ and SMH correlate **0.986–0.997**, and still **0.97+** after stripping
  market beta. Owning all three is one position at triple size.
- Grouping barely moves the effective-bets figure, which sits near **2 out of 10**.
  That is not a bug — de-duplication removes funds that are the same *holding*, but
  the leaders' remaining commonality is a shared *factor*. Loosening the threshold
  does not fix it: at r ≥ 0.80 the value factor fund absorbs 44 others including all
  three semiconductor funds, which correlate with it purely as equities.

## Running it

Requires Python 3 with `numpy`, Node for the preview, and a
[Financial Modeling Prep](https://financialmodelingprep.com) API key.

```bash
export FMP_API_KEY=...        # API_KEY is also accepted
make all                      # full refresh, ~10 min cold
make preview                  # render in Chromium and assert the page works
```

Individual stages:

| stage | does |
| --- | --- |
| `01_universe.py` | vendor ETF list → US tickers → loose dollar-volume pre-filter |
| `02_history.py hist` | unadjusted daily bars (the correct basis for dollar volume) |
| `03_screen.py` | the liquidity screen above |
| `02_history.py adj` | split- and dividend-adjusted closes for survivors |
| `04_score.py` | both windows: score, return, vol, rank, excess, cash flag |
| `05_corr.py` | per-window correlation edges + return vectors for the page |
| `06_page.py` | inject the payload into `web/etf-momentum.html`, validate |

Fetch stages are **resumable** — completed symbol files are skipped, so re-running
retries only failures. Data lands in `./data`; override with `ETF_DATA`. To rebuild a
past snapshot, set `ETF_CUTOFF=YYYY-MM-DD`.

`make page` alone rebuilds everything downstream of the downloads, which is what you
want after editing `web/etf-momentum.html`.

### Analysis

```bash
python3 analysis/correlation_report.py SOXX SOXQ SMH     # any cluster
ETF_WINDOW=6 python3 analysis/correlation_report.py      # on the 6−1 window
```

Reports pairwise correlation, beta and tracking error, residual correlation after
removing market beta, effective independent bets, and a paired bootstrap on whether
the score ordering inside the cluster is real. (It generally is not: the 90% CI on a
12−1 score is about ±1.7, and ±2.6 on 6−1, so gaps under ~0.1 are noise. Comparisons
*between correlated funds* are much tighter, because their difference is precisely
measured.)

## Publishing

`06_page.py` emits a standalone file. It is published as a Claude artifact; republish
the same path to update in place. The page is a **snapshot** — every figure is fixed
at the close it was built from and never updates.

## Open decisions

Deliberately unresolved, recorded here so they are not lost:

- **Raw vs excess as the headline score.** Raw is what the screen currently shows.
  Excess is the more principled default — it fixes the cash-equivalent problem at the
  source instead of relying on the cash-like filter — and changes essentially nothing
  above ~10% volatility.
- **Whether to show the score's confidence interval.** The page prints two decimals,
  which reads more precisely than the estimate deserves, especially on 6−1.
- **Market-residual grouping.** Raw correlation cannot separate a sector bet from
  plain market exposure. Stripping the universe's first principal component (rather
  than a chosen equity benchmark) would handle mixed asset classes automatically —
  bonds and commodities load near zero on it and would barely move. Not built; it may
  also be that ~2 independent bets in the top 10 is simply true.
- **The 3% volatility cash cutoff** and the exclusion of 32 liquid funds that have
  6−1 history but not 12−1. Both are documented in the page.
