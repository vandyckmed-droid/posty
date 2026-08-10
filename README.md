# posty

A risk-adjusted momentum screen over every liquid US-listed ETF, built for a phone
screen. It ranks funds by excess return per unit of volatility, folds near-identical funds
together so the list shows *bets* rather than tickers, and reports how many
independent bets the top of the list actually contains.

The output is a single self-contained HTML page with all data embedded — no network
access at runtime, no backend.

## The score

For each fund, over a **formation window** that stops 21 trading sessions short of
today (the "−1", which sidesteps short-term reversal):

1. Daily log returns `r_t = ln(P_t / P_t−1)` on **split- and dividend-adjusted** closes
2. Annualized return = `sum(r) × 252/n`, less the T-bill return over the same window
3. Annualized volatility = `stdev(r) × √252`
4. **Score = (2) ÷ (3)**

Two windows, ranked over the same universe so they stay directly comparable:

| window | lookback | returns | reads as |
| --- | --- | --- | --- |
| **6−1** | `t−126 … t−21` | 105 | fresher trends, noisier estimate (default) |
| **12−1** | `t−252 … t−21` | 231 | the classic academic window, slower to turn |

The numerator is the return **in excess of cash**, using the 1–3 month T-bill fund's
own return over the same window, which makes the score a Sharpe ratio. Without that
subtraction T-bill funds win outright — SGOV scored 19.5 on the raw ratio, since a
near-riskless asset has a near-zero denominator and essentially all of its return
*was* the risk-free rate. Above ~10% volatility the adjustment is invisible. The
un-netted **raw score** is kept in each row's detail and as a sort.

Each row also carries a **90% confidence interval** from the Sharpe-ratio standard
error `√252 · √((1 + s²/2) / n)` — roughly ±1.7 on 12−1 and ±2.6 on 6−1. Gaps under
about 0.1 are noise. The exception: comparisons between *correlated* funds are far
sharper, because what matters is the error on their difference.

## Universe

Starting from the vendor's full ETF list, the screen keeps plain US-listed tickers
that clear one baseline liquidity bar:

- **median daily dollar volume ≥ $5M** over the last 63 sessions — median, not mean,
  so a single block trade cannot lift a thin fund through the gate
- **last close ≥ $5**
- **≥ 273 sessions of history**, so the longest formation window exists

Delisted tickers that still quote a stale last price drop out automatically: they
return no price history. As of the last build, 10,404 listed ETFs → 6,284 US-listed
→ 2,092 pre-screened → **1,058 ranked**, of which **594 shown by default** — stock
funds, excluding leveraged and inverse products. Every filter is one tap away.

Whether a fund holds shares is decided from its **sector mix**, not its label, because
the labels are unreliable: the vendor files SPDR Gold Shares under "Equity" while
reporting it as 100% cash-and-other. A fund counts as stocks when ≥60% of it sits in
real operating sectors, with a short list of asset classes (bonds, commodities,
alternatives, multi-asset) excluded outright. REITs are deliberately kept — they hold
listed companies. Spot-checked against GLD, TLT, SGOV, IBIT, USO and DBC (all
correctly excluded) and SOXX, VLUE, XBI, EWT, VNQ, EEM, DIVB, IYZ (all kept).

## Grouping and diversification

Funds that move with a better-ranked fund are folded into that fund's row, under one
of two definitions of "move with":

- **Same fund** — raw return correlation ≥ 0.95. Index twins: different wrappers
  around the same holdings.
- **Same bet** (default) — correlation ≥ 0.85 *after removing the market factor*. A
  theme held through different funds, issuers and gearing.

The market factor is not a chosen benchmark; it is the first principal component of
the window's own correlation matrix (≈47% of variance on 12−1, ≈52% on 6−1). That
matters because much of this universe is not equities: measured this way, Treasury
funds cluster with Treasury funds and bitcoin funds with bitcoin funds, with nothing
told what asset class it belongs to. Removing it separates a sector wager from plain
market exposure — semiconductors vs large-cap value falls from **0.52 raw to −0.18
adjusted**, while semiconductors against each other barely move (0.99 → 0.98).

Membership is measured **against the representative**, never chained transitively, so
a group cannot drift into a different bet. Correlations are recomputed per window.

Each group flags **cheaper** when a member costs less than the fund heading it, since
the ranking cannot see fees at all. That gap is often the only thing separating two
funds making the identical bet: SOXQ charges 0.19% against SOXX at 0.33% and SMH at
0.35%, for semiconductor exposure correlated 0.98–1.00.

### Holdings

Every FMP holdings endpoint returns 402 on this plan (`etf/holdings`,
`funds/disclosure`, `funds/disclosure-holders-latest`), so stage 5 goes to the
primary source: each fund's **Form N-PORT filing with the SEC**, which is public,
free and authoritative. Ticker, name, weight and country per position.

Two details that are easy to get wrong:

- **Amendments restate old periods.** Taking the newest *filing* lands on stale data —
  SOXX filed an `NPORT-P/A` in July 2026 covering September 2025. The stage takes the
  newest **original** `NPORT-P` instead, which gives March 2026.
- **Issuers disclose different identifiers.** First Trust tags every position with a
  ticker; iShares and Vanguard give only an ISIN. Because those overlap across funds,
  the filings that carry both are harvested into an ISIN→ticker map and used to name
  the rest — no extra requests.

N-PORT is quarterly and published ~60 days after the period it covers, so holdings run
a few months behind. The reporting date is carried through and displayed above every
list. Alongside them, stage 4 supplies annual fee, fund size, position count, asset
class, issuer, **sector mix** and **country mix**; the country figures cross-check
against a third-party terminal (CIBR reads 89% United States in both).

The readout reports `N² / ΣΣ|r_ij|` over the top rows shown — the number of unrelated
holdings carrying the same risk as that basket. Absolute values matter: an inverse
fund is a perfect hedge against its own long, which is one bet expressed twice, not
free diversification.

The bets figure deliberately uses **raw** correlation, not market-adjusted: raw is
what your money actually experiences.

Two findings this surfaced, both documented in the page's own method section:

- SOXX, SOXQ and SMH correlate **0.986–0.997**, and still **0.98** after removing the
  market. Owning all three is one position at triple size.
- **No grouping setting moves the effective-bets figure**, which sits near 2 out of
  10 — market-adjusted grouping included. Folding duplicates changes *which* ten funds
  you see, not how much they overlap; the fund promoted from beneath a folded twin
  tends to be about as correlated with the rest. The top of a momentum screen is
  genuinely one or two trades wearing ten tickers. That is a fact about the market in
  this window, not an artifact to engineer away.

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
| `04_profile.py` | fee, size, holdings count, issuer, sector mix per fund |
| `05_holdings.py` | top positions and weights from SEC N-PORT filings |
| `06_score.py` | both windows: score, return, vol, rank, excess, cash flag |
| `07_corr.py` | per-window correlation edges + return vectors for the page |
| `08_page.py` | inject the payload into `web/etf-momentum.html`, validate |

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

## Curated run

A second, deliberately narrow build: a fixed list of sector and thematic ETFs ranked by
one hardwired score, with no filters to set.

```bash
export ETF_DATA=data-curated ETF_UNIVERSE=universe/curated.txt
make all
python3 pipeline/08_page.py web/etf-curated.html $ETF_DATA/etf-curated.build.html
node tools/preview-curated.mjs $ETF_DATA/etf-curated.build.html $ETF_DATA
```

`ETF_UNIVERSE` pins the universe to that file and switches the pipeline's behaviour:
stage 1 skips discovery entirely, stage 3 **measures liquidity but stops gating on it**
(the list is the universe), and stage 5 fetches holdings for every name regardless of
how the vendor classifies it. The risk-free reference (BIL) is fetched but never
ranked, since a curated list has no reason to contain a T-bill fund.

The score is a fixed 50/50 blend: `0.5 × (12−1 return ÷ sigma) + 0.5 × (6−1 return ÷
sigma)`, using the same window conventions as the main screen. Here the numerator is
the plain return, as specified for this build; the T-bill-netted blend is carried as
`cbNet` and shown in each row's detail. The choice moves no fund more than 8 places.

Rows carry a normalised price path covering the full 12 months **including** the
skipped final month, drawn shaded so it reads as context. Each fund also gets its
`near`est relative — the one other fund in the universe that moves most like it once
the market factor is removed — which surfaces near-duplicate exposures without adding
a control.

## Publishing

`08_page.py` emits a standalone file. It is published as a Claude artifact; republish
the same path to update in place. The page is a **snapshot** — every figure is fixed
at the close it was built from and never updates.

## Open decisions

Deliberately unresolved, recorded here so they are not lost:

- **PC1 is refitted per window and per rebuild**, so "the market factor" is not a
  stable, nameable thing across snapshots the way a named index would be. Groups can
  therefore shift between rebuilds for reasons that have nothing to do with the funds.
  Worth watching once there are several snapshots to compare.
- **The 0.85 market-adjusted grouping threshold** was chosen by inspecting the groups
  it produces, not derived. It keeps semiconductors together (0.98) and biotech (0.88)
  while leaving large-cap value unmerged (0.55).
- **The 3% volatility cash cutoff** and the exclusion of 32 liquid funds that have
  6−1 history but not 12−1. Both are documented in the page. Cash-like funds are now
  tagged but shown by default, since netting out the T-bill return removes the reason
  to hide them.
