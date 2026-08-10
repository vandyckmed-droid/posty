"""Stage 3: the baseline liquidity screen.

Everything that survives here is tradeable enough that a momentum rank on it means
something. The median (not mean) dollar volume matters: one block trade should not
lift a thin fund through the gate.
"""
import statistics as st
import common as C

cand = {c['symbol']: c for c in C.load('candidates.json')}
longest = max(C.WINDOWS.values())
need = longest + C.SKIP + 1

rows, rejects = [], {'no_data': 0, 'short_history': 0, 'low_price': 0, 'illiquid': 0}

for sym, meta in cand.items():
    bars = C.bars_for(sym, 'hist')
    if not bars:
        rejects['no_data'] += 1          # delisted tickers still quote a stale price
        continue
    bars = [b for b in bars if b.get('volume') is not None]
    if len(bars) < need:
        rejects['short_history'] += 1
        continue
    if bars[-1]['close'] < C.MIN_PRICE:
        rejects['low_price'] += 1
        continue
    med = st.median([b['close'] * b['volume'] for b in bars[-C.LIQ_WINDOW:]])
    if med < C.MIN_DOLLAR_VOL:
        rejects['illiquid'] += 1
        continue
    rows.append({'symbol': sym, 'name': meta['name'], 'medDollarVol': med,
                 'price': bars[-1]['close'], 'lastBar': bars[-1]['date'],
                 'bars': len(bars)})

rows.sort(key=lambda r: -r['medDollarVol'])
C.save('liquid.json', rows)
print(f'passed: {len(rows):,}   rejects: {rejects}')
print(f'last completed session: {rows[0]["lastBar"] if rows else "n/a"}')
