"""Stage 6: risk-adjusted momentum over two formation windows.

Both windows skip the most recent 21 sessions (the "-1", sidestepping short-term
reversal) and differ only in how far back they reach:

    12-1  ->  trading days t-252 .. t-21   (231 daily returns)
     6-1  ->  trading days t-126 .. t-21   (105 daily returns)

Inside each window:
    ann_return = sum(daily log returns) * 252 / n
    ann_vol    = stdev(daily log returns) * sqrt(252)
    score      = ann_return / ann_vol

One universe serves both: every fund carries enough history for the longer window,
so no fund appears in one ranking and vanishes from the other.
"""
import math
import re
import statistics as st

import common as C

# Fund-name classifiers. Both are deliberately narrow: "Ultra Short Duration Bond"
# and "Long/Short Equity" are ordinary funds, while "UltraShort 20+ Year Treasury"
# and "Short QQQ" are daily-reset directional products.
MULT = r'(?<![a-z0-9])-?(?:1\.5|[2-9](?:\.\d)?)x\b'          # 2x, 3x, 1.5x, -3x (not 1x)
ULTRASHORT = r'\bultrashort\b(?!\s*(?:fixed|income|bond))'    # ProShares, not Dimensional
ULTRA = r'\bultra\b(?![\s-]?short)'                           # Ultra QQQ, not Ultra-Short Bond
DIR_SHORT = (r'(?<!ultra )(?<!ultra-)(?<!long/)(?<!long )\bshort\b'
             r'(?!\s*-?\s*(?:term|duration|maturity|bond|income|treasury|municipal|credit))')

LEV = re.compile('|'.join([MULT, ULTRASHORT, ULTRA, r'\bultrapro\b', r'\bleveraged\b']), re.I)
SHORT = re.compile('|'.join([r'\binverse\b', r'\bbear\b', ULTRASHORT, DIR_SHORT,
                             r'(?<![a-z0-9])-[1-9](?:\.\d)?x\b']), re.I)

liq = C.load('liquid.json')
longest = max(C.WINDOWS.values())
out, skipped = [], {'no_adj': 0, 'short_history': 0, 'bad_bars': 0}
excluded = []                       # named, with the reason, rather than silently dropped
_seen = {r['symbol'] for r in liq}
for c in C.load('candidates.json'):
    if c['symbol'] not in _seen:
        excluded.append([c['symbol'], 'no price data from the vendor'])

for r in liq:
    sym = r['symbol']
    bars = C.bars_for(sym, 'adj', 'adjClose')
    if not bars:
        skipped['no_adj'] += 1
        continue
    if len(bars) < longest + 1:
        skipped['short_history'] += 1
        excluded.append([sym, f'only {len(bars)} sessions, needs {longest + 1}'])
        continue

    name = r['name'] or ''
    rec = {'s': sym, 'n': name, 'dv': round(r['medDollarVol']), 'px': r['price'],
           'lev': bool(LEV.search(name)), 'inv': bool(SHORT.search(name))}
    if r.get('cat'):
        rec['cat'] = r['cat']
    if r.get('label'):
        rec['lab'] = r['label']
    rec.update(C.profile(sym))
    rec.update(C.holdings(sym))
    bad = False
    for key, total in C.WINDOWS.items():
        win = bars[-(total + 1):len(bars) - C.SKIP]
        closes = [b['adjClose'] for b in win]
        if len(closes) < 60 or any(c <= 0 for c in closes):
            bad = True
            break
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        if any(abs(x) > C.MAX_ABS_DAILY_LOGRET for x in rets):
            bad = True                       # unadjusted split, not a real move
            break
        n = len(rets)
        cum = sum(rets)
        ann_ret = cum * 252.0 / n
        ann_vol = st.stdev(rets) * math.sqrt(252.0)
        if ann_vol <= 1e-6:
            bad = True
            break
        rec['w' + key] = {
            'sc': round(ann_ret / ann_vol, 4),
            'ar': round(ann_ret, 5),
            'tr': round(math.expm1(cum), 5),     # plain compounded window return
            'av': round(ann_vol, 5),
            'obs': n,
            'cash': ann_vol < C.CASH_VOL,
            'w0': win[0]['date'],
            'w1': win[-1]['date'],
        }
    if bad:
        skipped['bad_bars'] += 1
        continue

    path = [b['adjClose'] for b in bars[-(longest + C.SKIP + 1):]]
    if len(path) > 8:
        step = max(1, len(path) // 60)
        pts = path[::step] + [path[-1]]
        base = pts[0] or 1.0
        rec['sp'] = [round(v / base * 100, 2) for v in pts]
        rec['spSkip'] = round(C.SKIP / len(path), 4)   # where the scored window ends
    out.append(rec)

# The headline score nets out the T-bill return, so that has to exist before anything
# is ranked -- ranking on the raw ratio would order the list differently from the way
# the page displays it. Computed independently per window.
meta_win = {}
for key in C.WINDOWS:
    w = 'w' + key
    by = {o['s']: o for o in out}
    rf_src = next((s for s in ('BIL', 'SGOV', 'SHV') if s in by), None)
    if rf_src:
        rf = by[rf_src][w]['ar']
    else:
        # A curated universe need not contain a T-bill fund. Rather than let the
        # risk-free leg silently collapse to zero, read the reference series that
        # stage 2 stores alongside the universe.
        lookback = C.WINDOWS[key]        # NOT `total`, which leaks from the fund loop
        ref = C.bars_for('BIL', 'adj', 'adjClose')
        rf, rf_src = 0.0, None
        if len(ref) >= lookback + 1:
            rwin = ref[-(lookback + 1):len(ref) - C.SKIP]
            rc = [b['adjClose'] for b in rwin]
            rf = sum(math.log(rc[i] / rc[i - 1]) for i in range(1, len(rc))) * 252.0 / (len(rc) - 1)
            rf_src = 'BIL (reference, not ranked)'
    for o in out:
        o[w]['xs'] = round((o[w]['ar'] - rf) / o[w]['av'], 4)
    out.sort(key=lambda x: -x[w]['xs'])
    for i, o in enumerate(out, 1):
        o[w]['rk'] = i
    # Meter scale for the headline (excess) score. Netting out the T-bill return
    # collapses the cash-proxy outliers, so the whole population can set the scale.
    ns = sorted(o[w]['xs'] for o in out)
    lo = min(-1.0, round(ns[int(len(ns) * 0.005)] - 0.2, 1))
    hi = round(ns[int(len(ns) * 0.995)] + 0.2, 1)
    meta_win[key] = {
        'label': f'{key}−1', 'lookback': C.WINDOWS[key], 'obs': out[0][w]['obs'],
        'windowStart': out[0][w]['w0'], 'windowEnd': out[0][w]['w1'],
        'rf': round(rf, 5), 'rfSource': rf_src,
        'cashCount': sum(1 for o in out if o[w]['cash']),
        'domain': [lo, hi],
    }
    m = meta_win[key]
    print(f"{key}-1: {m['windowStart']} -> {m['windowEnd']}  n={m['obs']}  "
          f"rf={rf:.2%} ({rf_src})  cash-like={m['cashCount']}  domain={[lo, hi]}")

# Combined score: a fixed 50/50 blend of the two windows, each leg being that
# window's return divided by that window's sigma, exactly as specified. The
# T-bill-netted blend is carried alongside for reference -- it costs each fund
# rf/sigma, so it penalises the low-volatility names and is not identical in rank.
for o in out:
    o['cb'] = round(sum(C.COMBINED_WEIGHTS[k] * o['w' + k]['sc'] for k in C.WINDOWS), 4)
    o['cbNet'] = round(sum(C.COMBINED_WEIGHTS[k] * o['w' + k]['xs'] for k in C.WINDOWS), 4)
out.sort(key=lambda x: -x['cb'])
for i, o in enumerate(out, 1):
    o['crk'] = i
cbs = sorted(o['cb'] for o in out)
meta_combined = {
    'weights': C.COMBINED_WEIGHTS,
    'domain': [min(-1.0, round(cbs[0] - 0.2, 1)), round(cbs[-1] + 0.2, 1)],
}

out.sort(key=lambda x: -x['cb'])                 # presentation order
for key in C.WINDOWS:
    for o in out:
        o['w' + key].pop('w0', None)             # identical for every fund; lives in meta
        o['w' + key].pop('w1', None)

try:
    provenance = C.load('universe.json')
except (OSError, ValueError):
    provenance = {}

C.save('ranked.json', {'meta': {
    'asOf': liq[0]['lastBar'] if liq else C.CUTOFF,
    'universe': provenance.get('vendorList'),
    'usListed': provenance.get('usListed'),
    'preScreened': len(C.load('candidates.json')),
    'liquidityPassed': len(liq), 'ranked': len(out),
    'minDollarVol': C.MIN_DOLLAR_VOL, 'minPrice': C.MIN_PRICE,
    'liqWindow': C.LIQ_WINDOW, 'skip': C.SKIP, 'cashVol': C.CASH_VOL,
    'win': meta_win, 'combined': meta_combined,
    'pinned': bool(C.curated_universe()),
    'universeSize': len(C.load('candidates.json')),
    'categories': len({o.get('cat') for o in out if o.get('cat')}) or None,
    'excluded': excluded,
}, 'rows': out})

print(f'\nranked: {len(out):,}   skipped: {skipped}')
for key in C.WINDOWS:
    w = 'w' + key
    top = sorted(out, key=lambda x: x[w]['rk'])[:5]
    print(f'top 5 on {key}-1: ' + ', '.join(f"{o['s']} {o[w]['xs']:.2f}" for o in top))
print('\ntop 12 combined (0.5 x 12-1 + 0.5 x 6-1):')
for o in sorted(out, key=lambda x: x['crk'])[:12]:
    print(f"  {o['crk']:>3} {o['s']:<5} {o['cb']:6.2f}  "
          f"(12-1 {o['w12']['sc']:5.2f} / 6-1 {o['w6']['sc']:5.2f})  {o.get('lab','')[:34]}")
