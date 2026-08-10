"""Stage 1: build the candidate universe.

Takes every ETF on the vendor's master list, keeps plain US-listed tickers, then
pre-filters on a single day's dollar volume. The cut here is deliberately loose --
today's session is partial, so it only exists to avoid pulling 15 months of history
for thousands of funds that obviously cannot clear the real screen in stage 3.
"""
import re
import common as C

PREFILTER_DOLLAR_VOL = 300_000
US_TICKER = re.compile(r'[A-Z]{2,5}\Z')

listing = C.get('etf-list')
print(f'vendor ETF list: {len(listing):,}')

names = {e['symbol']: e.get('name') or ''
         for e in listing
         if e.get('symbol') and US_TICKER.match(e['symbol'])}
print(f'US-listed plain tickers: {len(names):,}')

quotes = {}
symbols = list(names)
for i in range(0, len(symbols), 700):
    batch = symbols[i:i + 700]
    for row in C.get('batch-quote-short', symbols=','.join(batch)):
        quotes[row['symbol']] = row
print(f'quoted: {len(quotes):,}')

candidates = []
for sym, q in quotes.items():
    price, vol = q.get('price') or 0, q.get('volume') or 0
    if price >= C.MIN_PRICE and price * vol >= PREFILTER_DOLLAR_VOL:
        candidates.append({'symbol': sym, 'name': names[sym],
                           'price': price, 'dvToday': price * vol})

candidates.sort(key=lambda c: -c['dvToday'])
C.save('candidates.json', candidates)
C.save('universe.json', {'vendorList': len(listing), 'usListed': len(names),
                         'quoted': len(quotes), 'candidates': len(candidates),
                         'prefilterDollarVol': PREFILTER_DOLLAR_VOL})
print(f'candidates carried to history fetch: {len(candidates):,}')
