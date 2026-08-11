"""Correlation / redundancy assessment for a cluster of funds in the screen.

Usage:  python3 analysis/correlation_report.py [TICKER ...]
Defaults to the semiconductor cluster. Reports pairwise correlation, market-adjusted
residual correlation, effective independent bets, and a paired bootstrap on whether
the score ordering inside the cluster is real.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
import common as C                                    # noqa: E402

SKIP, TOTAL = C.SKIP, max(C.WINDOWS.values())
WKEY = os.environ.get('ETF_WINDOW', '12')
OBS = C.WINDOWS[WKEY] - SKIP
rows = {r['s']: r for r in C.load('ranked.json')['rows']}

TRIO = sys.argv[1:] or ['SOXX', 'SOXQ', 'SMH']
WIDER = ['FTXL', 'PSI', 'SOXX', 'SOXQ', 'SMH', 'XSD', 'SMHX']
REF = ['SPY', 'QQQ', 'XLK']


def series(sym):
    bars = C.bars_for(sym, 'adj', 'adjClose')
    win = bars[-(TOTAL + 1):len(bars) - SKIP]
    dates = [b['date'] for b in win][1:]
    c = np.array([b['adjClose'] for b in win], float)
    return dates[-OBS:], np.diff(np.log(c))[-OBS:]


ALL = TRIO + [s for s in WIDER if s not in TRIO] + REF
data, dates0 = {}, None
for s in ALL:
    if not (C.DATA / 'adj' / f'{s}.json').exists():
        print('missing', s)
        continue
    d, r = series(s)
    if dates0 is None:
        dates0 = d
    assert d == dates0, f'date misalignment {s}'
    data[s] = r

n = len(dates0)
print(f'{WKEY}-1 window {dates0[0]} -> {dates0[-1]}   n={n} daily returns\n')


def corr(syms):
    M = np.vstack([data[s] for s in syms])
    return np.corrcoef(M)


def show(syms, title):
    C = corr(syms)
    print(title)
    print('        ' + ''.join(f'{s:>7}' for s in syms))
    for i, s in enumerate(syms):
        print(f'  {s:<6}' + ''.join(f'{C[i, j]:7.3f}' for j in range(len(syms))))
    off = C[np.triu_indices(len(syms), 1)]
    print(f'  mean off-diagonal r = {off.mean():.3f}   min = {off.min():.3f}   max = {off.max():.3f}')
    ev = np.linalg.eigvalsh(C)[::-1]
    w = ev / ev.sum()
    neff = 1.0 / (w ** 2).sum()
    print(f'  PC1 explains {w[0]:6.1%} of variance | effective independent bets = {neff:.2f} of {len(syms)}\n')
    return C


show(TRIO, '=== Screenshot trio: daily log-return correlation ===')
show(WIDER, '=== Wider unlevered semiconductor cluster ===')
show(TRIO + REF, '=== Trio vs market / tech benchmarks ===')

# --- pairwise economics -------------------------------------------------
print('=== Pairwise: are the differences tradeable? ===')
print(f"{'pair':<14}{'corr':>7}{'beta':>7}{'trackErr':>10}{'retDiff':>9}{'scoreDiff':>10}")
for i in range(len(TRIO)):
    for j in range(i + 1, len(TRIO)):
        a, b = TRIO[i], TRIO[j]
        ra, rb = data[a], data[b]
        c = np.corrcoef(ra, rb)[0, 1]
        beta = np.cov(ra, rb)[0, 1] / rb.var(ddof=1)
        te = (ra - rb).std(ddof=1) * math.sqrt(252)
        rd = (ra.sum() - rb.sum()) * 252 / n
        sd = rows[a]['w' + WKEY]['sc'] - rows[b]['w' + WKEY]['sc']
        print(f'{a}/{b:<9}{c:7.3f}{beta:7.2f}{te:9.1%}{rd:9.1%}{sd:10.2f}')

# --- residual correlation after stripping market beta -------------------
print('\n=== Residual correlation after removing SPY beta (is it a sector bet or a market bet?) ===')
spy = data['SPY']
res = {}
for s in TRIO:
    b = np.cov(data[s], spy)[0, 1] / spy.var(ddof=1)
    res[s] = data[s] - b * spy
    r2 = np.corrcoef(data[s], spy)[0, 1] ** 2
    print(f'  {s:<6} beta to SPY = {b:4.2f}   R2 to SPY = {r2:5.1%}   idiosyncratic vol = {res[s].std(ddof=1)*math.sqrt(252):5.1%}')
R = np.corrcoef(np.vstack([res[s] for s in TRIO]))
print('  residual correlation matrix:')
print('        ' + ''.join(f'{s:>7}' for s in TRIO))
for i, s in enumerate(TRIO):
    print(f'  {s:<6}' + ''.join(f'{R[i, j]:7.3f}' for j in range(len(TRIO))))

# --- how separable are the scores? paired bootstrap ---------------------
print('\n=== Paired bootstrap: is the 2.27 / 2.19 / 2.18 ordering real? ===')
rng = np.random.default_rng(7)
M = np.vstack([data[s] for s in TRIO])
B = 20000
wins = np.zeros((3, 3))
top = np.zeros(3)
scores = np.zeros((B, 3))
for b in range(B):
    idx = rng.integers(0, n, n)              # resample DATES jointly -> keeps cross-correlation
    S = M[:, idx]
    ann = S.sum(axis=1) * 252 / n
    vol = S.std(axis=1, ddof=1) * math.sqrt(252)
    sc = ann / vol
    scores[b] = sc
    top[np.argmax(sc)] += 1
    for i in range(3):
        for j in range(3):
            if sc[i] > sc[j]:
                wins[i, j] += 1
print('  P(rank 1) :  ' + '   '.join(f'{s}={top[i]/B:5.1%}' for i, s in enumerate(TRIO)))
for i in range(3):
    for j in range(i + 1, 3):
        print(f'  P({TRIO[i]} > {TRIO[j]}) = {wins[i, j]/B:5.1%}')
for i, s in enumerate(TRIO):
    lo, hi = np.percentile(scores[:, i], [5, 95])
    print(f'  {s:<6} score {rows[s]["w" + WKEY]["sc"]:5.2f}   90% CI [{lo:5.2f}, {hi:5.2f}]')

# --- how much of the screen is this one cluster? ------------------------
print('\n=== Cluster concentration in the screen (as the screenshot was filtered) ===')
allr = [r for r in C.load('ranked.json')['rows']
        if not r['w' + WKEY]['cash'] and not r['lev'] and not r['inv'] and r['dv'] >= 100e6]
allr.sort(key=lambda x: -x['w' + WKEY]['sc'])
print(f'  universe at these filters: {len(allr)} funds')
for k in (10, 25, 50):
    sub = allr[:k]
    ns = sum(1 for x in sub if 'semiconductor' in x['n'].lower() or 'phlx' in x['n'].lower())
    print(f'  top {k:>3}: {ns} semiconductor funds ({ns/k:.0%})')
print('\n  top 12 rows the screenshot is drawn from:')
for i, x in enumerate(allr[:12], 1):
    print(f'   {i:>3} {x["s"]:<6}{x["w" + WKEY]["sc"]:6.2f}  {x["n"][:52]}')
