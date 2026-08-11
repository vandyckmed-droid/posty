"""Stage 1: every US-listed share, then a loose liquidity prefilter.

The universe deliberately does NOT come from the vendor's company screener. That
endpoint silently truncates: asked for every NYSE company it returns about 3,000
and omits, among others, Realty Income, Cboe, Vornado, Federal Realty, Camden and
National Storage -- real, large, liquid names, absent with no error. A screen built
on it would have a hole in it and never say so.

`stock-list` returns the full symbol master (~50,000 lines) and is used instead.
Exchange is not one of its fields, so the shape of the ticker does the first cut --
a plain alphabetic symbol is a US common line, a dotted or dashed one is a foreign
or preferred listing -- and a batch quote does the second.
"""
import re

import cfg as C

PLAIN = re.compile(r'^[A-Z]{1,5}$')

C.require_key()
master = C.get('stock-list')
print(f'symbol master: {len(master):,}')

# The master mixes funds in with companies -- SPY, QQQ, GLD and every leveraged
# single-stock product are all "stocks" to it. The ETF list is the authoritative
# subtraction; without it the top of the ranking fills up with index funds, which is
# the exact thing this build exists to avoid holding.
funds = {str(r.get('symbol') or '') for r in C.get('etf-list')}
print(f'funds to exclude: {len(funds):,}')

# Commodity trusts and closed-end funds are pooled vehicles that the ETF list does
# not cover, and they arrive named as such. The pattern is deliberately narrow:
# matching "Trust" alone would throw out most of the REIT market, since Camden
# Property Trust and Federal Realty Investment Trust are operating companies.
POOLED = re.compile(
    r'\b(ETF|ETNs?|SPDR|Fund)\b'
    r'|(?:Gold|Silver|Platinum|Palladium|Bitcoin|Ethereum|Physical|Currency\w*)'
    r'[\w\s]*\bTrust\b', re.I)

syms, names = [], {}
for row in master:
    s = str(row.get('symbol') or '')
    nm = str(row.get('companyName') or '')
    if not PLAIN.match(s) or s in funds or POOLED.search(nm):
        continue
    syms.append(s)
    names[s] = str(row.get('companyName') or '')
syms = sorted(set(syms))
print(f'plain US-style company tickers: {len(syms):,}')

# Batch quotes: one day of price and volume is enough to throw out the obviously
# untradeable before spending a history call on them. The real screen is stage 3,
# on a 63-session median, so this bar is set well below it on purpose.
quotes = {}
BATCH = 400
for i in range(0, len(syms), BATCH):
    chunk = syms[i:i + BATCH]
    try:
        for q in C.get('batch-quote-short', symbols=','.join(chunk)):
            quotes[str(q.get('symbol'))] = q
    except Exception as e:                          # noqa: BLE001
        print(f'  batch {i}: {str(e)[:70]}')
    if (i // BATCH) % 5 == 0:
        print(f'  quoted {len(quotes):,}/{len(syms):,}', flush=True)

cand = []
for s in syms:
    q = quotes.get(s)
    if not q:
        continue
    px = float(q.get('price') or 0)
    vol = float(q.get('volume') or 0)
    if px < C.MIN_PRICE or px * vol < C.PREFILTER:
        continue
    cand.append({'symbol': s, 'name': names.get(s, ''), 'px': px, 'dv': px * vol})

cand.sort(key=lambda r: -r['dv'])
C.save('candidates.json', cand)
print(f'quoted {len(quotes):,}  ->  {len(cand):,} candidates above '
      f'${C.PREFILTER/1e6:.0f}M of turnover')
