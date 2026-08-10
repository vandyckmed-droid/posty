#!/usr/bin/env python3
"""Inline data/momentum.json into artifact/template.html -> artifact/index.html."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "artifact", "template.html")
DATA = os.path.join(ROOT, "data", "momentum.json")
OUT = os.path.join(ROOT, "artifact", "index.html")


def main():
    with open(DATA) as fh:
        payload = json.load(fh)
    with open(TEMPLATE) as fh:
        html = fh.read()

    if "__DATA__" not in html:
        raise SystemExit("template is missing the __DATA__ placeholder")

    # </script> inside the JSON would close the tag early; escape it.
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    out = html.replace("__DATA__", blob)

    with open(OUT, "w") as fh:
        fh.write(out)
    print(f"wrote {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB, "
          f"{len(payload['rows'])} rows, data as of {payload['dataAsOf']})")


if __name__ == "__main__":
    main()
