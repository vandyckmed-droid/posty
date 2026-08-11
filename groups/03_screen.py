"""Stage 3: the liquidity screen, and the return matrix everything else is built on.

Median daily dollar volume over the last 63 sessions, not the mean, so one block
trade cannot lift a thin name through the gate. A stock also has to have traded on
every day of the formation window: a group's return series is only meaningful if its
members share a calendar.
"""
import json

import numpy as np

import cfg as C

adj = C.DATA / 'adj'
# Only what stage 1 currently nominates. The download directory is a cache and can
# hold symbols an earlier, looser universe pulled in -- index funds, for one.
wanted = {r['symbol'] for r in C.load('candidates.json')}
bars = {}
for path in sorted(adj.glob('*.json')):
    sym = path.stem
    if sym not in wanted:
        continue
    try:
        rows = json.loads(path.read_text() or '[]')
    except ValueError:
        continue
    if not isinstance(rows, list):
        continue
    rows = [b for b in rows
            if b.get('date', '') < C.CUTOFF and b.get('adjClose') and b.get('volume')]
    if len(rows) < max(C.WINDOWS.values()) + C.SKIP + 5:
        continue
    rows.sort(key=lambda b: b['date'])
    bars[sym] = rows
print(f'{len(bars):,} symbols with enough history')

cal = C.calendar(bars)
window = cal[-(max(C.WINDOWS.values()) + C.SKIP):-C.SKIP]
liq = cal[-C.LIQ_WINDOW:]
print(f'calendar {len(cal)} sessions; formation window {window[0]} .. {window[-1]} '
      f'({len(window)} closes, {len(window)-1} returns); skipping {C.SKIP}')

# Dollar volume on the adjusted close. A stock that split inside the window has its
# turnover restated by the split factor, which is the wrong basis in principle --
# but the screen is a gate at $25M, not a published figure, and the alternative is a
# second unadjusted download for every name to move a handful of borderline cases.
liquid = []
for sym, rows in bars.items():
    m = {b['date']: b for b in rows}
    have = [m[d] for d in liq if d in m]
    if len(have) < C.LIQ_WINDOW * 0.7:
        continue
    med = float(np.median([b['adjClose'] * b['volume'] for b in have]))
    last = rows[-1]['adjClose']
    if med < C.MIN_DOLLAR_VOL or last < C.MIN_PRICE:
        continue
    liquid.append({'symbol': sym, 'dv': round(med), 'px': round(last, 2)})

keep = {r['symbol'] for r in liquid}
syms, R = C.returns({s: b for s, b in bars.items() if s in keep}, window)
priced = set(syms)
liquid = [r for r in liquid if r['symbol'] in priced]
liquid.sort(key=lambda r: -r['dv'])

C.save('liquid.json', liquid)
np.save(C.DATA / 'returns.npy', R)
C.save('returns_index.json', {'syms': syms, 'window': window})
print(f'{len(liquid):,} liquid names (median daily $ volume >= '
      f'${C.MIN_DOLLAR_VOL/1e6:.0f}M, last >= ${C.MIN_PRICE:.0f})')
print(f'return matrix: {R.shape[0]:,} x {R.shape[1]}')
