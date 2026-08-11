"""Stage 4: turn the written taxonomy into groups the returns actually support.

The taxonomy in `universe/stock_themes.txt` is a hypothesis about what belongs
together. This stage tests it, in three steps:

1. **Drop members that do not move with their own group.** A name correlating under
   +0.05 with the rest of its theme, once the market is removed, is in the wrong
   place -- it is being carried by the label, not by the behaviour.

2. **Split a group only when the split is real.** Any finer partition mechanically
   raises within-group correlation, so "the sub-groups score higher" proves nothing.
   The test is whether *this particular* cut beats a random cut of the same shape:
   the members are reshuffled into buckets of identical sizes 1,500 times, and the
   split is kept only if it lands above the 95th percentile of that distribution. On
   this universe roughly a third of themes contain a real internal boundary -- gas
   E&Ps do not trade with oil E&Ps, rails do not trade with truckers -- and the rest
   are homogeneous, where a finer taxonomy would be inventing detail.

3. **Flag groups that never cohere.** Below +0.15 a group is a story, not a bet.
   The most fashionable theme in the market fails this test: obesity/GLP-1 names
   share a narrative and not a price.

Nothing here is fitted to returns in a way that could flatter the result -- the
membership was written first, and every step below can only remove or divide.
"""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

import cfg as C

idx = C.load('returns_index.json')
syms = idx['syms']
I = {s: i for i, s in enumerate(syms)}
R = np.load(C.DATA / 'returns.npy')
dv = {r['symbol']: r['dv'] for r in C.load('liquid.json')}

RAW, ADJ, pc1 = C.market_adjusted(R)
print(f'{len(syms):,} names, {R.shape[1]} returns, market factor = '
      f'{pc1*100:.0f}% of variance')

rng = np.random.default_rng(20260811)


def ids(v):
    return [I[t] for t in v]


def partition_cohesion(parts):
    """Pair-weighted mean correlation inside a partition of one group."""
    tot = wt = 0.0
    for v in parts:
        if len(v) < 2:
            continue
        p = len(v) * (len(v) - 1) / 2
        tot += C.cohesion(ADJ, ids(v)) * p
        wt += p
    return (tot / wt) if wt else float('nan')


def split_survives(members, parts):
    sizes = sorted((len(p) for p in parts), reverse=True)
    if len(sizes) < 2:
        return False, float('nan')
    obs = partition_cohesion(parts)
    if np.isnan(obs):
        return False, obs
    draws = []
    for _ in range(C.SPLIT_TRIALS):
        shuffled = list(rng.permutation(members))
        cut, k = [], 0
        for s in sizes:
            cut.append(shuffled[k:k + s])
            k += s
        c = partition_cohesion(cut)
        if not np.isnan(c):
            draws.append(c)
    return float((np.array(draws) < obs).mean()) > C.SPLIT_PCTILE, obs


def hcut(members, k):
    """Cut a theme into k parts, with no member left behind.

    Average-linkage regularly peels off one or two names into a part too small to
    stand on its own. Discarding them would silently shrink the universe -- Citigroup
    fell out of money-center banks that way -- so a stranded member is reattached to
    whichever surviving part it actually correlates with most.
    """
    sub = ADJ[np.ix_(ids(members), ids(members))]
    D = np.clip(1 - sub, 0, 2)
    np.fill_diagonal(D, 0)
    lab = fcluster(linkage(squareform(D, checks=False), 'average'), k, 'maxclust')
    out = {}
    for t, l in zip(members, lab):
        out.setdefault(int(l), []).append(t)
    parts = [p for p in out.values() if len(p) >= C.MIN_GROUP]
    orphans = [t for p in out.values() if len(p) < C.MIN_GROUP for t in p]
    if not parts:
        return []
    for t in orphans:
        fit = [float(ADJ[I[t], ids(p)].mean()) for p in parts]
        parts[int(np.argmax(fit))].append(t)
    return parts


def divide(theme, members, depth=0):
    """Split a group as long as each split keeps passing the test.

    One pass is not enough: a 90-name theme that divides into 68 and 22 has not
    really been resolved, and the 68 usually divides again. Recursion stops when no
    cut survives, so the depth is decided by the returns rather than chosen.
    """
    if len(members) < 2 * C.MIN_GROUP or depth >= 5:
        return [members]
    best = None
    for k in (2, 3):
        parts = hcut(members, k)
        if len(parts) < 2:
            continue
        ok, obs = split_survives(members, parts)
        if ok and (best is None or obs > best[1]):
            best = (parts, obs)
    if not best:
        return [members]
    splits.append({'theme': theme, 'n': len(members), 'depth': depth,
                   'before': round(C.cohesion(ADJ, ids(members)), 3),
                   'after': round(best[1], 3),
                   'into': [len(p) for p in best[0]]})
    out = []
    for p in best[0]:
        out += divide(theme, p, depth + 1)
    return out


def label(theme, members):
    """A split subgroup is named for its two most-traded members, not a number."""
    lead = sorted(members, key=lambda t: -dv.get(t, 0))[:2]
    return f'{theme} — ' + '/'.join(lead)


live = set(syms)
groups, dropped, splits, missing, claimed = [], [], [], [], {}
for theme, wrote in C.themes():
    # A stock belongs to exactly one group -- otherwise the equal-weight baskets
    # overlap and the effective-bets figure quietly double-counts. Ties go to the
    # theme that appears first in the file, which is alphabetical, so the outcome is
    # stable across rebuilds rather than depending on dictionary order.
    members = [t for t in wrote if t in live and t not in claimed]
    for t in members:
        claimed[t] = theme
    missing += [t for t in wrote if t not in live]
    if len(members) < C.MIN_GROUP:
        continue

    if len(members) >= 4:
        sub = ADJ[np.ix_(ids(members), ids(members))]
        avg = (sub.sum(1) - 1) / (len(members) - 1)
        keep = [t for t, a in zip(members, avg) if a >= C.DROP_MEMBER]
        for t, a in zip(members, avg):
            if a < C.DROP_MEMBER:
                dropped.append({'sym': t, 'theme': theme, 'corr': round(float(a), 3)})
        members = keep
    if len(members) < C.MIN_GROUP:
        continue

    parts = divide(theme, members)
    if len(parts) == 1:
        groups.append({'name': theme, 'theme': theme, 'members': members,
                       'split': False})
    else:
        for p in parts:
            groups.append({'name': label(theme, p), 'theme': theme, 'members': p,
                           'split': True})

for g in groups:
    ii = ids(g['members'])
    g['coh'] = round(C.cohesion(ADJ, ii), 3)
    g['cohRaw'] = round(C.cohesion(RAW, ii), 3)
    g['bets'] = round(C.effective_bets(RAW, ii), 2)
    g['n'] = len(g['members'])
    g['weak'] = g['coh'] < C.MIN_COHESION

groups.sort(key=lambda g: -g['coh'])

# Group-level correlation: the closest relative of each group, so a near-duplicate
# bet is visible without anybody having to go looking for it. Built after the sort,
# so row i of the saved matrix is group i of the saved order.
P = np.array([np.mean([R[I[t]] for t in g['members']], axis=0) for g in groups])
PZ = (P - P.mean(1, keepdims=True)) / P.std(1, keepdims=True)
GC = np.corrcoef(PZ)
np.fill_diagonal(GC, -2)
for i, g in enumerate(groups):
    j = int(GC[i].argmax())
    g['near'] = [groups[j]['name'], round(float(GC[i, j]), 2)]
np.fill_diagonal(GC, 1.0)

C.save('groups.json', {'groups': groups, 'pc1': round(pc1, 4),
                       'dropped': dropped, 'splits': splits,
                       'unlisted': sorted(set(missing))})
np.save(C.DATA / 'group_corr.npy', GC)
C.save('group_order.json', [g['name'] for g in groups])

covered = {t for g in groups for t in g['members']}
pw = sum(g['coh'] * g['n'] * (g['n'] - 1) / 2 for g in groups) / \
     sum(g['n'] * (g['n'] - 1) / 2 for g in groups)
print(f'{len(groups)} groups covering {len(covered):,} of {len(syms):,} liquid names '
      f'({len(covered)*100//len(syms)}%)')
print(f'pair-weighted cohesion {pw:+.4f}   median {np.median([g["coh"] for g in groups]):+.3f}'
      f'   below +{C.MIN_COHESION:.2f}: {sum(1 for g in groups if g["weak"])}')
print(f'{len(dropped)} members dropped, {len(splits)} themes split, '
      f'{len(set(missing))} written tickers not in the liquid set')
for s in sorted(splits, key=lambda s: s['before'] - s['after'])[:12]:
    print(f'  split {s["theme"]:38s} {s["into"]}  {s["before"]:+.3f} -> {s["after"]:+.3f}')
