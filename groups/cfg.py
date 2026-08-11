"""Shared configuration for the self-designed stock groups build.

This is a second product on the same data plumbing as the ETF screen. Instead of
ranking funds somebody else assembled, it assembles its own: a written taxonomy of
the liquid US tape, tested against returns, then ranked as equal-weight baskets.

HTTP, caching and file conventions are reused from the ETF pipeline so there is one
implementation of each; everything below is what differs.
"""
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
import common as P                                  # noqa: E402

get, save, load, require_key = P.get, P.save, P.load, P.require_key
DATA, CUTOFF, HISTORY_FROM = P.DATA, P.CUTOFF, P.HISTORY_FROM
SKIP, WINDOWS, LIQ_WINDOW = P.SKIP, P.WINDOWS, P.LIQ_WINDOW
MAX_ABS_DAILY_LOGRET = P.MAX_ABS_DAILY_LOGRET

# A single share is far thinner than a fund, and a group is only worth building if
# every member can actually be bought, so the bar is set higher than the ETF screen's
# $5M. At $25M a day the liquid US tape is about 1,600 names.
MIN_DOLLAR_VOL = float(os.environ.get('STOCK_MIN_DOLLAR_VOL', 25_000_000))
MIN_PRICE = 5.0
PREFILTER = 0.4 * MIN_DOLLAR_VOL       # one day's turnover, before the real screen

THEMES_FILE = os.environ.get('STOCK_THEMES', 'universe/stock_themes.txt')

# Grouping rules. Each one is a decision the analysis had to justify:
MIN_GROUP = 3          # below this a "group" is a handful of names, not a bet
DROP_MEMBER = 0.05     # a member correlating under this with its own group is out
MIN_COHESION = 0.15    # a group below this is a label, not a bet -- flagged, not shown
SPLIT_PCTILE = 0.95    # a split must beat this share of random cuts of the same shape
SPLIT_TRIALS = 1500
COMBINED_WEIGHTS = {'12': 0.5, '6': 0.5}


def themes():
    """[(name, [tickers])] from the committed taxonomy."""
    out = []
    with open(THEMES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '|' not in line:
                continue
            name, rest = line.split('|', 1)
            out.append((name.strip(), sorted(set(rest.split()))))
    return out


def calendar(bars):
    """Consensus trading days.

    Taking the calendar from whichever symbol has the longest history is wrong: at
    least one vendor series carries a stray Saturday bar, and every stock that
    (correctly) has no such session then looks like it is missing a day and gets
    dropped. A day is real when most of the universe traded on it.
    """
    cnt = Counter(b['date'] for d in bars.values() for b in d)
    if not cnt:
        return []
    floor = 0.8 * max(cnt.values())
    return sorted(d for d, c in cnt.items() if c >= floor)


def returns(bars, window):
    """(symbols, log-return matrix) over an explicit list of trading days."""
    syms, rows = [], []
    for s in sorted(bars):
        m = {b['date']: b for b in bars[s]}
        if any(d not in m for d in window):
            continue
        px = np.array([m[d]['adjClose'] for d in window], float)
        if (px <= 0).any():
            continue
        r = np.diff(np.log(px))
        if np.abs(r).max() > MAX_ABS_DAILY_LOGRET:   # an unadjusted split
            continue
        syms.append(s)
        rows.append(r)
    return syms, np.array(rows)


def market_adjusted(R):
    """Correlation before and after removing the market factor.

    The factor is the first principal component of the universe's own correlation
    matrix, not a chosen index -- nothing is told what sector it belongs to. Across
    single stocks it is a much smaller thing than it is across funds: about 16% of
    variance here against ~47% in the ETF universe, because a fund is already a
    diversified basket and a share is not.
    """
    Z = (R - R.mean(1, keepdims=True)) / R.std(1, keepdims=True)
    C = np.corrcoef(Z)
    w, V = np.linalg.eigh(C)
    pc1 = V[:, -1]
    f = pc1 @ Z / np.sqrt((pc1 ** 2).sum())
    f = (f - f.mean()) / f.std()
    beta = (Z @ f) / len(f)
    E = Z - beta[:, None] * f[None, :]
    E = (E - E.mean(1, keepdims=True)) / E.std(1, keepdims=True)
    return C, np.corrcoef(E), float(w[-1] / w.sum())


def cohesion(M, ids):
    """Mean pairwise correlation inside a group. Unrelated stocks score 0."""
    if len(ids) < 2:
        return float('nan')
    sub = M[np.ix_(ids, ids)]
    iu = np.triu_indices(len(ids), 1)
    return float(sub[iu].mean())


def effective_bets(M, ids):
    """N^2 / sum|r| -- how many unrelated names carry this basket's risk.

    Absolute values: a perfectly negatively correlated pair is one bet expressed
    twice, not free diversification.
    """
    n = len(ids)
    if n < 2:
        return float(n)
    return float(n * n / np.abs(M[np.ix_(ids, ids)]).sum())
