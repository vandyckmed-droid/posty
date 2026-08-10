"""Stage 7: correlation features for de-duplication and the diversification readout.

Correlation has to be measured on whichever formation window is active, so the raw
daily log returns are stored ONCE (the 6-1 window is exactly the last 105 returns of
the 12-1 series, since both end at t-21) and the page standardizes the slice it needs.

  vec    - raw log returns, int16, base64. Standardized per window in the browser,
           after which a dot product is the exact correlation and the effective-bets
           figure is a cheap pairwise sum.
  edges  - exact pairwise r above 0.90, precomputed PER WINDOW. These are the only
           pairs de-duplication can act on, and scanning 558k pairs in JS on a phone
           would be far too slow to do live.
"""
import base64
import json
import math

import numpy as np

import common as C

LONGEST = max(C.WINDOWS.values())
# A window of T sessions ending SKIP days back spans T+1-SKIP closes, so T-SKIP returns.
WIN_OBS = {k: v - C.SKIP for k, v in C.WINDOWS.items()}
EDGE_CUT = C.EDGE_CUT
RESID_CUT = C.RESID_CUT

payload = C.load('ranked.json')
rows = payload['rows']


def window(sym):
    bars = C.bars_for(sym, 'adj', 'adjClose')
    return bars[-(LONGEST + 1):len(bars) - C.SKIP]


cal = [b['date'] for b in window('SPY')][1:]
pos = {d: i for i, d in enumerate(cal)}
n = len(cal)
assert n == WIN_OBS['12'], (n, WIN_OBS['12'])

R, vrow = [], []
for i, r in enumerate(rows):
    w = window(r['s'])
    d = [b['date'] for b in w]
    c = [b['adjClose'] for b in w]
    v = np.full(n, np.nan)
    for t in range(1, len(w)):
        j = pos.get(d[t])
        if j is not None and c[t - 1] > 0:
            v[j] = math.log(c[t] / c[t - 1])
    if np.isnan(v).sum() > 5:
        r['v'] = -1                      # no aligned history -> never grouped
        continue
    v[np.isnan(v)] = 0.0
    r['v'] = len(R)
    R.append(v)
    vrow.append(i)

R = np.array(R)
print(f'correlatable {len(R)} of {len(rows)}   calendar {cal[0]} -> {cal[-1]}  n={n}')

# Store each fund standardized over the FULL series, not raw. Correlation is
# scale-invariant, so pre-scaling per fund changes nothing downstream -- but it stops
# a single global quantization step from starving low-volatility funds of levels
# (raw returns span 0.1% to 15% a day across this universe). The page re-standardizes
# whichever slice it needs, which is exact for the 6-1 sub-window too.
Zfull = (R - R.mean(1, keepdims=True)) / R.std(1, ddof=1, keepdims=True)
SCALE = int(32000 / np.abs(Zfull).max())
Q = np.round(Zfull * SCALE).astype(np.int16)
payload['vec'] = base64.b64encode(Q.astype('<i2').tobytes()).decode()
payload['vecN'] = n
payload['vecRows'] = len(R)
print(f'vectors: {len(R)}x{n} int16 (scale {SCALE}) -> {len(payload["vec"])/1024:.0f} KB base64')


def unit(M):
    """standardize rows, then scale so a dot product is exactly the correlation"""
    Z = (M - M.mean(1, keepdims=True)) / M.std(1, ddof=1, keepdims=True)
    return Z / math.sqrt(M.shape[1] - 1)


def edge_list(corr, cut):
    iu = np.triu_indices(len(corr), 1)
    mask = corr[iu] >= cut
    flat = []
    for a, b, rr in zip(iu[0][mask], iu[1][mask], corr[iu][mask]):
        flat += [vrow[a], vrow[b], int(round(rr * 1000))]
    return flat, int(mask.sum())


payload['edges'] = {}
payload['redges'] = {}
payload['pc1'] = {}
for key, obs in WIN_OBS.items():
    exact = unit(R[:, n - obs:])
    quant = unit(Q[:, n - obs:].astype(float))
    corr = np.clip(exact @ exact.T, -1, 1)
    err = np.abs(np.clip(quant @ quant.T, -1, 1) - corr).max()
    iu = np.triu_indices(len(R), 1)

    # Raw correlation: catches funds that are the same HOLDING (index twins).
    payload['edges'][key], nraw = edge_list(corr, EDGE_CUT)

    # Market-adjusted correlation: catches funds that are the same BET.
    # The common factor is the first principal component of this window's own
    # correlation matrix, not a chosen benchmark -- so nothing is measured against
    # an index it has no business being compared to, and non-equity funds sort
    # themselves out (Treasuries cluster with Treasuries, bitcoin with bitcoin).
    evals, evecs = np.linalg.eigh(corr)
    factor = evecs[:, -1] @ exact
    factor /= np.linalg.norm(factor)
    resid = exact - np.outer(exact @ factor, factor)
    resid /= np.linalg.norm(resid, axis=1, keepdims=True)
    rcorr = np.clip(resid @ resid.T, -1, 1)
    payload['redges'][key], nres = edge_list(rcorr, RESID_CUT)
    payload['pc1'][key] = round(float(evals[-1] / len(corr)), 4)

    print(f'{key}-1: obs={obs}  quantization err={err:.2e}  '
          f'PC1 explains {payload["pc1"][key]:.1%}')
    print(f'      raw edges >={EDGE_CUT}: {nraw:,} '
          f'({len(json.dumps(payload["edges"][key]))/1024:.0f} KB)   '
          f'market-adj edges >={RESID_CUT}: {nres:,} '
          f'({len(json.dumps(payload["redges"][key]))/1024:.0f} KB)')

payload['edgeCut'] = EDGE_CUT
payload['residCut'] = RESID_CUT
path = C.save('ranked.json', payload)
print(f'\n{path} {path.stat().st_size/1024:.0f} KB')

# ---- reference values ---------------------------------------------------
idx = {rows[vrow[i]]['s']: i for i in range(len(R))}


def neff(syms, key):
    U = unit(R[:, n - WIN_OBS[key]:])
    a = U[[idx[s] for s in syms if s in idx]]
    ac = np.abs(np.clip(a @ a.T, -1, 1))
    return len(a) ** 2 / ac.sum()


for key in WIN_OBS:
    w = 'w' + key
    pool = sorted([r for r in rows if not r[w]['cash'] and r['dv'] >= 5e6],
                  key=lambda x: -x[w]['sc'])
    print(f'check {key}-1: trio N_eff={neff(["SOXX","SOXQ","SMH"], key):.3f}   '
          f'top10 ungrouped N_eff={neff([r["s"] for r in pool[:10]], key):.3f}')
