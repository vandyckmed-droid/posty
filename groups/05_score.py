"""Stage 5: rank the groups as equal-weight baskets, and score every member.

Each group is treated as a fund we built ourselves: hold every member at the same
weight, rebalanced daily, and score the resulting return series exactly the way the
ETF screen scores a real fund -- annualised return over annualised volatility, on a
formation window that stops 21 sessions short of today.

Equal weight is the whole point. A vendor's sector fund is a market-cap bet wearing
a sector label: buy a semiconductor ETF and most of what you own is the two largest
members. Weighting the members equally makes the group a statement about the theme
rather than about its biggest constituent.
"""
import json

import numpy as np

import cfg as C

adj = C.DATA / 'adj'
data = C.load('groups.json')
groups = data['groups']
liquid = {r['symbol']: r for r in C.load('liquid.json')}
names = {r['symbol']: r.get('name', '') for r in C.load('candidates.json')}

bars = {}
for sym in {t for g in groups for t in g['members']}:
    rows = json.loads((adj / f'{sym}.json').read_text() or '[]')
    rows = [b for b in rows if b.get('date', '') < C.CUTOFF and b.get('adjClose')]
    rows.sort(key=lambda b: b['date'])
    bars[sym] = rows

cal = C.calendar(bars)
as_of = cal[-1]
print(f'{len(bars):,} member histories, latest close {as_of}')

WIN = {k: cal[-(v + C.SKIP):-C.SKIP] for k, v in C.WINDOWS.items()}
FULL = cal[-(max(C.WINDOWS.values()) + C.SKIP):]        # includes the skipped month


def series(sym, days):
    m = {b['date']: b for b in bars[sym]}
    if any(d not in m for d in days):
        return None
    px = np.array([m[d]['adjClose'] for d in days], float)
    if (px <= 0).any():
        return None
    return px


def score(r):
    """Annualised return over annualised volatility, from daily log returns."""
    ann_r = float(r.sum() * 252 / len(r))
    ann_v = float(r.std() * np.sqrt(252))
    return ann_r, ann_v, (ann_r / ann_v if ann_v else 0.0)


member_rets = {}
for key, days in WIN.items():
    for sym in bars:
        px = series(sym, days)
        if px is not None:
            member_rets[(sym, key)] = np.diff(np.log(px))

out = []
for g in groups:
    row = {k: g[k] for k in ('name', 'theme', 'n', 'coh', 'cohRaw', 'bets',
                             'near', 'weak', 'split')}
    ok = True
    for key, days in WIN.items():
        rs = [member_rets[(t, key)] for t in g['members'] if (t, key) in member_rets]
        if len(rs) < C.MIN_GROUP:
            ok = False
            break
        p = np.mean(rs, axis=0)
        ann_r, ann_v, sc = score(p)
        row['w' + key] = {'sc': round(sc, 3), 'ret': round(ann_r, 4),
                          'vol': round(ann_v, 4), 'n': len(rs)}
    if not ok:
        continue
    row['cb'] = round(sum(C.COMBINED_WEIGHTS[k] * row['w' + k]['sc'] for k in C.WINDOWS), 3)

    # Normalised equal-weight path over the full year, including the skipped month,
    # drawn shaded on the page so the "-1" is visible as context rather than hidden.
    paths = [series(t, FULL) for t in g['members']]
    paths = [p / p[0] for p in paths if p is not None]
    if paths:
        path = np.mean(paths, axis=0)
        step = max(1, len(path) // 80)
        row['sp'] = [round(float(x), 4) for x in path[::step]]
        row['spSkip'] = len([d for d in FULL[::step] if d > WIN['12'][-1]])

    mem = []
    for t in sorted(g['members'], key=lambda t: -liquid.get(t, {}).get('dv', 0)):
        m = {'t': t, 'n': names.get(t, '')[:44],
             'dv': round(liquid.get(t, {}).get('dv', 0) / 1e6)}
        for key in C.WINDOWS:
            r = member_rets.get((t, key))
            if r is not None:
                m['s' + key] = round(score(r)[2], 2)
        mem.append(m)
    row['mem'] = mem
    out.append(row)

out.sort(key=lambda r: -r['cb'])
for i, r in enumerate(out, 1):
    r['rank'] = i

# How many independent bets sit at the top of the ranking? This is the question the
# ETF screen kept answering badly, and building our own groups does not fix it: the
# top of a momentum list is a small number of trades wearing many names, whoever
# assembled the baskets.
order = C.load('group_order.json')
GC = np.load(C.DATA / 'group_corr.npy')
pos = {nm: i for i, nm in enumerate(order)}
top = [pos[r['name']] for r in out if r['name'] in pos]
readout = {}
for k in (5, 10, 20):
    sel = top[:k]
    sub = np.abs(GC[np.ix_(sel, sel)])
    readout[str(k)] = round(float(len(sel) ** 2 / sub.sum()), 2)

payload = {
    'asOf': as_of,
    'built': C.CUTOFF,
    'pc1': data['pc1'],
    'liquid': len(liquid),
    'covered': sum(r['n'] for r in out),
    'groups': out,
    'bets': readout,
    'splits': data['splits'],
    'dropped': data['dropped'],
    'minDv': C.MIN_DOLLAR_VOL,
    'minCoh': C.MIN_COHESION,
    'dropCut': C.DROP_MEMBER,
    'weights': C.COMBINED_WEIGHTS,
    'windows': {k: len(v) - 1 for k, v in WIN.items()},
    'skip': C.SKIP,
}
C.save('ranked.json', payload)
print(f'{len(out)} groups ranked, {payload["covered"]:,} member slots')
print(f'effective bets: top 5 {readout["5"]}, top 10 {readout["10"]}, top 20 {readout["20"]}')
for r in out[:10]:
    print(f'  {r["rank"]:2d}. {r["cb"]:5.2f}  coh {r["coh"]:+.2f}  n={r["n"]:2d}  {r["name"]}')
