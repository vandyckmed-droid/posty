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

# ---------------------------------------------------------------------------
# Naming. Issuers differ in what they disclose: First Trust tags every position with
# a ticker, iShares and Vanguard give only an ISIN. The resolution is kept OUT of the
# saved filings -- those stay exactly as parsed -- and written to a separate map that
# stage 6 applies when it reads them. That way a naming mistake is fixed by re-running
# this step, with no re-fetching and no risk of a bad value becoming indistinguishable
# from one the filing actually provided.
CACHE = 'isin_lookup.json'
try:
    resolved = C.load(CACHE) or {}
except (OSError, ValueError):
    resolved = {}

files = sorted(out.glob('*.json'))
seed = os.environ.get('ETF_ISIN_SEED')
sources = [pathlib.Path(seed)] if seed else []
sources.append(out)

harvested = 0
for src in sources:
    for f in src.glob('*.json'):
        try:
            h = json.loads(f.read_text())
        except ValueError:
            continue
        for p in h.get('top', []):
            if p.get('t') and p.get('i') and p['i'] not in resolved:
                resolved[p['i']] = p['t']       # the filing named it itself
                harvested += 1
print(f'harvested {harvested:,} ISIN -> ticker pairs from filings that name their own')

todo = sorted({p['i'] for f in files
               for p in (json.loads(f.read_text()).get('top') or [])
               if p.get('i') and not p.get('t') and p['i'] not in resolved})
if todo:
    print(f'resolving {len(todo):,} remaining ISINs directly')
    rlock = Lock()

    def resolve(isin):
        try:
            hit = C.get('search-isin', isin=isin)
        except Exception:                           # noqa: BLE001
            hit = None
        sym = ''
        if isinstance(hit, list) and hit:
            # A US security often lists abroad too, and the first match is not
            # reliably the primary line: Labcorp's ISIN returns 0JSY.L (London)
            # ahead of LH. Prefer a plain US-style ticker, then the largest listing.
            def rank(row):
                t = str(row.get('symbol') or '')
                return (0 if ('.' not in t and '-' not in t) else 1,
                        -float(row.get('marketCap') or 0))
            sym = str(sorted(hit, key=rank)[0].get('symbol') or '')
        with rlock:
            resolved[isin] = sym                    # '' recorded too, so we ask once
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(resolve, todo))

C.save(CACHE, resolved)
have = sum(1 for v in resolved.values() if v)
print(f'ISIN map: {have:,} named of {len(resolved):,} known')
