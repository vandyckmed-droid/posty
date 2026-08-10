"""Stage 4: fund profiles - cost, size, and what each fund actually is.

Per-stock holdings sit behind a higher API tier, so this pulls what the plan does
expose. That turns out to cover the decision the screen sets up: once grouping says
two funds are the same bet, the fee is what separates them, and the spread is real
(SOXQ 0.19% vs SOXX 0.33% for the same semiconductor exposure).
"""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import common as C

rows = C.load('liquid.json')
out = C.DATA / 'profile'
out.mkdir(parents=True, exist_ok=True)

lock, done, failed = Lock(), [0], []


def grab(row):
    sym = row['symbol']
    path = out / f'{sym}.json'
    cpath = out / f'{sym}.country.json'
    try:
        if not (path.exists() and path.stat().st_size > 20):
            path.write_text(json.dumps(C.get('etf/info', symbol=sym)))
        if not cpath.exists():
            cpath.write_text(json.dumps(C.get('etf/country-weightings', symbol=sym)))
    except Exception as e:                          # noqa: BLE001
        with lock:
            failed.append((sym, str(e)[:100]))
    with lock:
        done[0] += 1
        if done[0] % 250 == 0:
            print(f'{done[0]}/{len(rows)}', flush=True)


print(f'profiles: {len(rows):,} symbols')
with ThreadPoolExecutor(max_workers=12) as ex:
    list(ex.map(grab, rows))

C.save('profile_failures.json', failed)
have = sum(1 for r in rows if (out / f"{r['symbol']}.country.json").exists())
print(f'done {done[0]:,}  failures: {len(failed)}  with country data: {have:,}')
if failed:
    print('re-run this stage to retry them; completed files are skipped')
