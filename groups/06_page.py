"""Stage 6: inject the ranked groups into the page and check the result.

Same contract as the ETF build: a standalone fragment with every figure embedded,
no network access at runtime. The checks are derived from the file rather than
hardcoded, so a new element or token is covered without anyone remembering to add it
here -- which is how the ETF page's missing-id bug was eventually caught.
"""
import json
import re
import sys
from pathlib import Path

import cfg as C

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else 'web/stock-groups.html')
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else C.DATA / 'stock-groups.build.html'

payload = C.load('ranked.json')
payload.pop('dropped_detail', None)

blob = json.dumps(payload, separators=(',', ':'))
# a company name containing "</script>" would otherwise close the tag early
blob = blob.replace('<', '\\u003c').replace('>', '\\u003e')

html = SRC.read_text()
assert '__DATA__' in html, 'placeholder missing'
html = html.replace('__DATA__', blob)
OUT.write_text(html)
kb = OUT.stat().st_size / 1024
print(f'built {OUT}  {kb:.0f} KB  groups={len(payload["groups"])}')

errs = []
if '__DATA__' in html:
    errs.append('placeholder not replaced')
for tag in ('<!doctype', '<html', '<head', '<body'):
    if re.search(re.escape(tag) + r'[\s>]', html, re.I):
        errs.append('skeleton tag present: ' + tag)
if kb > 16 * 1024:
    errs.append('over 16MB')

root = re.search(r':root\s*\{(.*?)\}', html, re.S).group(1)
defined = set(re.findall(r'--([\w-]+)\s*:', root))
used = set(re.findall(r'var\(--([\w-]+)\)', html))
if used - defined:
    errs.append('tokens used but not defined in bare :root: ' + ', '.join(sorted(used - defined)))

ids = set(re.findall(r'id="([\w-]+)"', html))
for want in sorted(set(re.findall(r"getElementById\('([\w-]+)'\)", html))
                   | set(re.findall(r"\$\('([\w-]+)'\)", html))):
    if want not in ids:
        errs.append('missing id: ' + want)

# Every key the page reads off a group must be present on every group, or a row
# silently renders as "undefined" -- which is exactly how the ETF page shipped a
# broken sector block once.
need = sorted(set(re.findall(r'\bg\.([a-zA-Z][\w]*)', html)) - {'split'})
for key in need:
    missing = [g['name'] for g in payload['groups'] if key not in g]
    if missing:
        errs.append(f'{len(missing)} groups missing "{key}" (e.g. {missing[0]})')

print('CHECKS:', 'ok' if not errs else 'FAILED')
for e in errs:
    print('  !', e)
sys.exit(1 if errs else 0)
