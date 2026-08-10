"""Stage 2: unadjusted daily bars for every candidate.

Unadjusted closes are the correct basis for dollar volume (price x shares actually
traded). Returns are computed later from adjusted closes instead.
"""
import sys
import common as C
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

SUBDIR = sys.argv[1] if len(sys.argv) > 1 else 'hist'
ENDPOINT = 'historical-price-eod/full' if SUBDIR == 'hist' else 'historical-price-eod/dividend-adjusted'
SOURCE = 'candidates.json' if SUBDIR == 'hist' else 'liquid.json'

rows = C.load(SOURCE)
out = C.DATA / SUBDIR
out.mkdir(parents=True, exist_ok=True)

lock, done, failed = Lock(), [0], []


def grab(row):
    sym = row['symbol']
    path = out / f'{sym}.json'
    if path.exists() and path.stat().st_size > 50:
        with lock:
            done[0] += 1
        return
    try:
        data = C.get(ENDPOINT, symbol=sym, **{'from': C.HISTORY_FROM, 'to': C.CUTOFF})
        path.write_text(__import__('json').dumps(data))
    except Exception as e:                          # noqa: BLE001
        with lock:
            failed.append((sym, str(e)[:100]))
    with lock:
        done[0] += 1
        if done[0] % 250 == 0:
            print(f'{done[0]}/{len(rows)}', flush=True)


print(f'{SUBDIR}: {len(rows):,} symbols, {C.HISTORY_FROM} -> {C.CUTOFF}')
with ThreadPoolExecutor(max_workers=12) as ex:
    list(ex.map(grab, rows))

C.save(f'{SUBDIR}_failures.json', failed)
print(f'done {done[0]:,}  failures: {len(failed)}')
if failed:
    print('re-run this stage to retry them; completed files are skipped')
