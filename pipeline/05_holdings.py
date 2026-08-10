"""Stage 5: what each fund actually holds, from SEC N-PORT filings.

The price vendor gates holdings behind a higher tier, so this goes to the source
instead. Every US-registered fund files Form N-PORT, and the filings are public,
free and authoritative -- they carry ticker, name, weight and country per position.

The tradeoff is vintage: N-PORT is quarterly and published about 60 days after the
period it covers, so holdings run a few months behind. For an index fund that is
mostly fine -- the roster barely moves, only the weights drift -- and the reporting
date is carried through and shown on the page rather than glossed over.

SEC asks for a descriptive User-Agent and fair access; this stays well inside the
published 10 requests/second guidance.
"""
import json
import os
import pathlib
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Semaphore

import common as C

UA = 'posty-etf-research/1.0 (contact: vandyck.med@gmail.com)'
TOP_N = 14                       # positions carried into the page
gate = Semaphore(6)              # concurrent SEC requests
out = C.DATA / 'holdings'
out.mkdir(parents=True, exist_ok=True)


def sec(url, retries=3):
    for attempt in range(retries):
        with gate:
            req = urllib.request.Request(url, headers={'User-Agent': UA,
                                                       'Accept-Encoding': 'gzip, deflate'})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read()
                    if r.headers.get('Content-Encoding') == 'gzip':
                        import gzip
                        raw = gzip.decompress(raw)
                    return raw.decode('utf-8', 'replace')
            except Exception:                       # noqa: BLE001
                if attempt == retries - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))
    return ''


def tag(blob, name):
    m = re.search(rf'<(?:\w+:)?{name}[^>]*>(.*?)</(?:\w+:)?{name}>', blob, re.S)
    return m.group(1).strip() if m else None


print('fetching SEC ticker -> series map')
mf = json.loads(sec('https://www.sec.gov/files/company_tickers_mf.json'))
fields = mf['fields']
si, ci, ti = fields.index('seriesId'), fields.index('cik'), fields.index('symbol')
series = {}
for row in mf['data']:
    series.setdefault(row[ti], (row[ci], row[si]))
print(f'  {len(series):,} fund tickers mapped')

# Only equity funds: a broad bond fund can carry thousands of line items, and the
# question this answers -- which companies drove the move -- is a stock question.
# A pinned universe overrides that: the list was curated deliberately, so every name
# on it gets looked up regardless of how the vendor classifies it.
if C.curated_universe():
    targets = [r['symbol'] for r in C.load('liquid.json')]
else:
    targets = [r['symbol'] for r in C.load('liquid.json')
               if C.profile(r['symbol']).get('stk')]
print(f'targets: {len(targets):,} stock funds')

lock, done, stats = Lock(), [0], {'ok': 0, 'no_series': 0, 'no_filing': 0, 'error': 0}


def grab(sym):
    path = out / f'{sym}.json'
    if path.exists():
        with lock:
            done[0] += 1
            stats['ok'] += 1
        return
    try:
        if sym not in series:
            with lock:
                stats['no_series'] += 1
            path.write_text(json.dumps({'err': 'no series id'}))
            return
        cik, sid = series[sym]
        feed = sec('https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany'
                   f'&CIK={sid}&type=NPORT-P&dateb=&owner=include&count=8&output=atom')
        # Take the newest ORIGINAL filing. An NPORT-P/A amendment restates an older
        # period, so trusting the newest filing date lands on stale holdings: SOXX
        # filed an amendment in July 2026 covering September 2025.
        href = None
        for entry in re.findall(r'<entry>(.*?)</entry>', feed, re.S):
            ftype = re.search(r'<filing-type>(.*?)</filing-type>', entry)
            if ftype and ftype.group(1).strip() == 'NPORT-P':
                href = re.search(r'<filing-href>(.*?)</filing-href>', entry)
                break
        if not href:
            with lock:
                stats['no_filing'] += 1
            path.write_text(json.dumps({'err': 'no original NPORT-P filing'}))
            return
        doc = href.group(1).rsplit('/', 1)[0] + '/primary_doc.xml'
        xml = sec(doc)

        positions = []
        for blob in re.findall(r'<invstOrSec>(.*?)</invstOrSec>', xml, re.S):
            pct = tag(blob, 'pctVal')
            if not pct:
                continue
            try:
                pct = float(pct)
            except ValueError:
                continue
            tick = re.search(r'<ticker\s+value="([^"]*)"', blob)
            tick = (tick.group(1) or '').strip() if tick else ''
            if tick.upper() in ('N/A', 'NA', 'NONE'):
                tick = ''
            isin = re.search(r'<isin\s+value="([^"]*)"', blob)
            positions.append({
                't': tick,
                'i': (isin.group(1) or '').strip() if isin else '',
                'n': (tag(blob, 'name') or '').strip()[:60],
                'p': round(pct, 3),
                'c': (tag(blob, 'invCountry') or '').strip(),
                'eq': (tag(blob, 'assetCat') or '').strip() == 'EC',
            })
        positions.sort(key=lambda x: -x['p'])
        path.write_text(json.dumps({
            'asOf': tag(xml, 'repPdDate'),
            'total': len(positions),
            'eqPct': round(sum(p['p'] for p in positions if p['eq']), 1),
            'top': positions[:TOP_N],
        }))
        with lock:
            stats['ok'] += 1
    except Exception as e:                          # noqa: BLE001
        with lock:
            stats['error'] += 1
        print(f'  {sym}: {str(e)[:80]}', flush=True)
    finally:
        with lock:
            done[0] += 1
            if done[0] % 100 == 0:
                print(f'{done[0]}/{len(targets)}  {stats}', flush=True)


with ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(grab, targets))

print(f'done {done[0]:,}  {stats}')

# Issuers differ in what they disclose: First Trust tags every position with a ticker,
# iShares and Vanguard give only an ISIN. Since the two overlap across funds, the
# filings that carry both are enough to name the ones that do not -- no extra requests.
isin_to_ticker = {}
# A small universe harvests few pairs of its own, so an existing holdings directory
# from a wider run can seed the map. Purely a naming aid; no figures come from it.
seed = os.environ.get('ETF_ISIN_SEED')
if seed:
    for f in pathlib.Path(seed).glob('*.json'):
        try:
            h = json.loads(f.read_text())
        except ValueError:
            continue
        for p in h.get('top', []):
            if p.get('t') and p.get('i'):
                isin_to_ticker.setdefault(p['i'], p['t'])
    print(f'seeded {len(isin_to_ticker):,} ISIN -> ticker pairs from {seed}')

files = sorted(out.glob('*.json'))
for f in files:
    try:
        h = json.loads(f.read_text())
    except ValueError:
        continue
    for p in h.get('top', []):
        if p.get('t') and p.get('i'):
            isin_to_ticker.setdefault(p['i'], p['t'])
print(f'harvested {len(isin_to_ticker):,} ISIN -> ticker pairs from the filings themselves')

filled = missing = 0
for f in files:
    try:
        h = json.loads(f.read_text())
    except ValueError:
        continue
    if not h.get('top'):
        continue
    touched = False
    for p in h['top']:
        if not p.get('t'):
            hit = isin_to_ticker.get(p.get('i'))
            if hit:
                p['t'] = hit
                filled += 1
                touched = True
            else:
                missing += 1
    if touched:
        f.write_text(json.dumps(h))
print(f'backfilled {filled:,} tickers; {missing:,} positions still unnamed')
