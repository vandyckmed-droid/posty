#!/usr/bin/env python3
"""Build the momentum dataset that backs the static artifact.

Pipeline
--------
1. Pull the U.S.-listed common-stock universe from the FMP company screener.
2. Download ~16 months of daily EOD bars for every candidate.
3. Compute 63-day average daily dollar volume (ADDV), keep the top 500.
4. Compute 12-1 and 6-1 momentum, percentile-rank both, blend 50/50.
5. Compute 126-day annualized realized volatility (used for inverse-vol weights).
6. Emit data/momentum.json -- the only thing the artifact ever sees.

The API key is read from the API_KEY environment variable and never leaves this
process: it is not written to the output file and not shipped to the browser.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "https://financialmodelingprep.com/stable"
API_KEY = os.environ.get("API_KEY") or os.environ.get("FMP_API_KEY")
if not API_KEY:
    sys.exit("API_KEY (or FMP_API_KEY) must be set in the environment")

EXCHANGES = ["NYSE", "NASDAQ", "AMEX"]

ADDV_WINDOW = 63       # trading days for average daily dollar volume
VOL_WINDOW = 126       # trading days of returns for realized volatility
SKIP_MONTH = 21        # trading days treated as "1 month"
LOOKBACK_12M = 252     # trading days treated as "12 months"
LOOKBACK_6M = 126      # trading days treated as "6 months"
TRADING_DAYS_YEAR = 252

UNIVERSE_SIZE = 500    # ranked by ADDV
DISPLAY_SIZE = 100     # ranked by combined momentum
PROFILE_CHECK = 800    # ADDV-ranked names verified as non-ADR common stock

# Preferred shares (BAC-PB), warrants (XYZ-WT), rights (XYZ-RT), units (XYZ-UN).
# Class-share suffixes such as BRK-B / BF-B are genuine common stock and stay.
NON_COMMON = re.compile(r"-(P[A-Z]?|WT[A-Z]?|WS[A-Z]?|RT|R|U|UN|CL)$", re.I)

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "momentum.json")


# --------------------------------------------------------------------------- io

def _get(url, tries=4):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "momentum-build"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 - transient network/API hiccups
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after {tries} tries: {last}")


def api(path, **params):
    params["apikey"] = API_KEY
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return _get(f"{BASE}/{path}?{query}")


# --------------------------------------------------------------------- universe

def fetch_universe():
    """Actively-traded U.S. common stocks on NYSE / NASDAQ / AMEX."""
    seen, rows = set(), []
    for exchange in EXCHANGES:
        batch = api(
            "company-screener",
            exchange=exchange,
            country="US",
            isEtf="false",
            isFund="false",
            isActivelyTrading="true",
            limit=10000,
        )
        for row in batch:
            sym = row.get("symbol") or ""
            if not sym or sym in seen:
                continue
            if "." in sym or NON_COMMON.search(sym):
                continue
            if row.get("isEtf") or row.get("isFund"):
                continue
            seen.add(sym)
            rows.append(row)
        print(f"  {exchange}: {len(batch)} rows", flush=True)
    return rows


# ---------------------------------------------------------------------- history

def fetch_history(symbol, start, end):
    try:
        bars = api("historical-price-eod/full", symbol=symbol, **{"from": start, "to": end})
    except Exception:
        return symbol, None
    if not isinstance(bars, list) or not bars:
        return symbol, None
    # FMP returns newest-first; we want oldest-first.
    bars.sort(key=lambda b: b["date"])
    return symbol, bars


def stdev(xs):
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return var ** 0.5


def summarize(bars):
    """Reduce a price series to the handful of statistics the artifact needs."""
    closes = [b.get("close") for b in bars]
    volumes = [b.get("volume") or 0 for b in bars]
    if any(c is None or c <= 0 for c in closes):
        return None
    n = len(closes)
    if n < LOOKBACK_12M + SKIP_MONTH + 1:
        return None

    addv = sum(c * v for c, v in zip(closes[-ADDV_WINDOW:], volumes[-ADDV_WINDOW:])) / ADDV_WINDOW

    p_recent = closes[-(SKIP_MONTH + 1)]          # ~1 month ago
    p_12m = closes[-(LOOKBACK_12M + SKIP_MONTH + 1)]
    p_6m = closes[-(LOOKBACK_6M + SKIP_MONTH + 1)]

    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(n - VOL_WINDOW, n)]
    sd = stdev(rets)
    if sd is None:
        return None

    return {
        "addv": addv,
        "ret12_1": p_recent / p_12m - 1.0,
        "ret6_1": p_recent / p_6m - 1.0,
        "vol126": sd * (TRADING_DAYS_YEAR ** 0.5),
        "price": closes[-1],
        "asOf": bars[-1]["date"],
        # 12 monthly closes (~1 per 21 trading days) for the sparkline
        "spark": [round(closes[i], 4) for i in range(max(0, n - 253), n, 21)],
    }


# ------------------------------------------------------------------------ ranks

def percentile_ranks(values):
    """Average-rank percentile in [0, 100]; ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    denom = max(len(values) - 1, 1)
    return [r / denom * 100.0 for r in ranks]


# ------------------------------------------------------------------------- main

def main():
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=560)).isoformat()
    end = today.isoformat()

    print("1/5 universe", flush=True)
    universe = fetch_universe()
    meta = {r["symbol"]: r for r in universe}
    print(f"  {len(universe)} candidate common stocks", flush=True)

    print("2/5 price history", flush=True)
    symbols = list(meta)
    stats, t0 = {}, time.time()
    with ThreadPoolExecutor(16) as pool:
        futures = [pool.submit(fetch_history, s, start, end) for s in symbols]
        for done, fut in enumerate(futures, 1):
            sym, bars = fut.result()
            if bars:
                s = summarize(bars)
                if s:
                    stats[sym] = s
            if done % 500 == 0:
                print(f"  {done}/{len(symbols)}  ({time.time() - t0:.0f}s)", flush=True)
    print(f"  {len(stats)} symbols with a full history", flush=True)

    print("3/5 liquidity screen", flush=True)
    ranked = sorted(stats, key=lambda s: stats[s]["addv"], reverse=True)

    # Verify the liquid head really is non-ADR common equity before cutting to 500.
    head = ranked[:PROFILE_CHECK]
    profiles = {}
    with ThreadPoolExecutor(16) as pool:
        def profile(sym):
            try:
                res = api("profile", symbol=sym)
                return sym, (res[0] if res else None)
            except Exception:
                return sym, None
        for sym, prof in pool.map(profile, head):
            profiles[sym] = prof

    eligible = []
    for sym in head:
        prof = profiles.get(sym)
        if prof and (prof.get("isAdr") or prof.get("isEtf") or prof.get("isFund")):
            continue
        eligible.append(sym)
    top = eligible[:UNIVERSE_SIZE]
    print(f"  {len(head) - len(eligible)} non-common-equity names dropped; "
          f"universe = {len(top)}", flush=True)

    print("4/5 momentum ranks", flush=True)
    r12 = percentile_ranks([stats[s]["ret12_1"] for s in top])
    r6 = percentile_ranks([stats[s]["ret6_1"] for s in top])

    rows = []
    for i, sym in enumerate(top):
        st = stats[sym]
        m = meta.get(sym, {})
        prof = profiles.get(sym) or {}
        rows.append({
            "ticker": sym,
            "name": m.get("companyName") or prof.get("companyName") or sym,
            "sector": m.get("sector") or prof.get("sector") or "Unclassified",
            "industry": m.get("industry") or prof.get("industry") or "",
            "exchange": m.get("exchangeShortName") or prof.get("exchange") or "",
            "marketCap": m.get("marketCap") or prof.get("marketCap") or 0,
            "price": round(st["price"], 4),
            "ret12_1": st["ret12_1"],
            "ret6_1": st["ret6_1"],
            "pct12_1": r12[i],
            "pct6_1": r6[i],
            "score": 0.5 * r12[i] + 0.5 * r6[i],
            "addv": st["addv"],
            "vol126": st["vol126"],
            "spark": st["spark"],
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    display = rows[:DISPLAY_SIZE]

    print("5/5 write", flush=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataAsOf": max(stats[s]["asOf"] for s in top),
        "universeSize": len(top),
        "displaySize": len(display),
        "candidatesScreened": len(stats),
        "params": {
            "addvWindow": ADDV_WINDOW,
            "volWindow": VOL_WINDOW,
            "skipMonth": SKIP_MONTH,
            "lookback12m": LOOKBACK_12M,
            "lookback6m": LOOKBACK_6M,
            "tradingDaysYear": TRADING_DAYS_YEAR,
        },
        "rows": [
            {
                "r": r["rank"],
                "t": r["ticker"],
                "n": r["name"],
                "s": r["sector"],
                "i": r["industry"],
                "x": r["exchange"],
                "mc": r["marketCap"],
                "p": round(r["price"], 2),
                "m12": round(r["ret12_1"], 6),
                "m6": round(r["ret6_1"], 6),
                "p12": round(r["pct12_1"], 3),
                "p6": round(r["pct6_1"], 3),
                "sc": round(r["score"], 3),
                "dv": round(r["addv"]),
                "v": round(r["vol126"], 6),
                "sp": r["spark"],
            }
            for r in display
        ],
    }

    out = os.path.abspath(OUT_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"  wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)", flush=True)


if __name__ == "__main__":
    main()
