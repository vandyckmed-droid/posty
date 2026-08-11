"""Stage 2: split- and dividend-adjusted daily bars for every candidate.

Resumable -- a symbol already on disk is skipped, so a re-run retries only what
failed. The dividend-adjusted endpoint carries volume alongside the adjusted close,
which is what stage 3 screens on.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import cfg as C

out = C.DATA / 'adj'
out.mkdir(parents=True, exist_ok=True)

cand = [r['symbol'] for r in C.load('candidates.json')]
todo = [s for s in cand if not (out / f'{s}.json').exists()]
print(f'{len(cand):,} candidates, {len(todo):,} to fetch')

lock, done, fails = Lock(), [0], []


def grab(sym):
    try:
        bars = C.get('historical-price-eod/dividend-adjusted',
                     symbol=sym, **{'from': C.HISTORY_FROM})
        (out / f'{sym}.json').write_text(json.dumps(bars if isinstance(bars, list) else []))
    except Exception as e:                          # noqa: BLE001
        with lock:
            fails.append(sym)
        print(f'  {sym}: {str(e)[:70]}', flush=True)
    finally:
        with lock:
            done[0] += 1
            if done[0] % 250 == 0:
                print(f'  {done[0]:,}/{len(todo):,}', flush=True)


with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(grab, todo))

C.save('history_fails.json', fails)
print(f'done {done[0]:,}, {len(fails)} failed')
