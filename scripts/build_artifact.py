#!/usr/bin/env python3
"""Assemble src/ into the single self-contained artifact/index.html.

The artifact must ship as one file with no external requests, but the source is
kept modular: styles and app modules are separate files, concatenated here in
filename order (the numeric prefixes are the dependency order). Everything is
wrapped in one IIFE, so each module is a plain `const X = (() => {...})()` and
name collisions are the only coupling to watch.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data", "momentum.json")
OUT = os.path.join(ROOT, "artifact", "index.html")


def concat(folder, ext):
    d = os.path.join(SRC, folder)
    parts = []
    for name in sorted(os.listdir(d)):
        if name.endswith(ext):
            with open(os.path.join(d, name)) as fh:
                parts.append(f"/* {folder}/{name} */\n{fh.read().strip()}")
    return "\n\n".join(parts), sorted(n for n in os.listdir(d) if n.endswith(ext))


def main():
    with open(DATA) as fh:
        payload = json.load(fh)
    with open(os.path.join(SRC, "shell.html")) as fh:
        shell = fh.read()

    css, css_files = concat("styles", ".css")
    js, js_files = concat("app", ".js")

    # "</" inside the JSON would close the script tag early.
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")

    bundle = (
        "<script>\n(function(){\n\"use strict\";\n"
        f"const DATA = {blob};\n\n{js}\n\nMain.init();\n"
        "})();\n</script>"
    )

    html = shell.replace("{{STYLES}}", f"<style>\n{css}\n</style>").replace("{{SCRIPTS}}", bundle)

    with open(OUT, "w") as fh:
        fh.write(html)

    print(f"wrote {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB)")
    print(f"  {len(css_files)} stylesheets, {len(js_files)} modules, "
          f"{len(payload['rows'])} rows, data as of {payload['dataAsOf']}")


if __name__ == "__main__":
    main()
