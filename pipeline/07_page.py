import json
import re
import sys
from pathlib import Path

import common as C

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else 'web/etf-momentum.html')
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else C.DATA / 'etf-momentum.build.html'

payload = C.load('ranked.json')
# compact keys already; strip fields the page never reads
for r in payload['rows']:
    r.pop('n_', None)

blob = json.dumps(payload, separators=(',', ':'))
# a fund name containing "</script>" would otherwise close the tag early
blob = blob.replace('<', '\\u003c').replace('>', '\\u003e')

html = SRC.read_text()
assert '__DATA__' in html, 'placeholder missing'
html = html.replace('__DATA__', blob)

OUT.write_text(html)
kb = OUT.stat().st_size / 1024
print(f'built {OUT}  {kb:.0f} KB  rows={len(payload["rows"])}')

# --- sanity checks ------------------------------------------------------
errs = []
if '__DATA__' in html:
    errs.append('placeholder not replaced')
for tag in ('<!doctype', '<html', '<head', '<body'):
    if re.search(re.escape(tag) + r'[\s>]', html, re.I):
        errs.append('skeleton tag present: ' + tag)
if kb > 16 * 1024:
    errs.append('over 16MB')

# every color token used must be defined in the bare :root block
root = re.search(r':root\s*\{(.*?)\}', html, re.S).group(1)
defined = set(re.findall(r'--([\w-]+)\s*:', root))
used = set(re.findall(r'var\(--([\w-]+)\)', html))
missing = used - defined
if missing:
    errs.append('tokens used but not defined in bare :root: ' + ', '.join(sorted(missing)))

# every element that references an id in JS must exist in the markup
ids = set(re.findall(r'id="([\w-]+)"', html))
for want in ('asof', 'uni', 'total', 'medline', 'list', 'more', 'empty', 'grpline',
             'q', 'f-cash', 'f-lev', 'f-inv', 'cashn', 'rfn', 'data',
             'ro-shown', 'ro-grp', 'ro-bets', 'pc1n', 'rescut', 'ro-grp-l'):
    if want not in ids:
        errs.append('missing id: ' + want)

print('CHECKS:', 'ok' if not errs else 'FAILED')
for e in errs:
    print('  !', e)
