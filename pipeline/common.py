"""Shared configuration and HTTP helpers for the ETF momentum pipeline."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = 'https://financialmodelingprep.com/stable'

# Financial Modeling Prep key. FMP_API_KEY is preferred; API_KEY is accepted so the
# pipeline runs unchanged in environments that export the generic name.
API_KEY = os.environ.get('FMP_API_KEY') or os.environ.get('API_KEY')

# Working directory for downloaded and derived data. Everything under it is
# reproducible from the API and is git-ignored.
DATA = Path(os.environ.get('ETF_DATA', 'data'))

# Today's session is still in progress, so every stage excludes bars dated on or
# after this. Override to rebuild a past snapshot.
CUTOFF = os.environ.get('ETF_CUTOFF') or date.today().isoformat()

# ~15 months of calendar days, enough for the 252-session lookback plus the 21-day
# skip plus weekends, holidays and a safety margin.
HISTORY_FROM = os.environ.get('ETF_HISTORY_FROM') or (
    date.fromisoformat(CUTOFF) - timedelta(days=470)).isoformat()

# Screen thresholds
MIN_DOLLAR_VOL = 5_000_000     # median daily $ volume over LIQ_WINDOW sessions
MIN_PRICE = 5.0
LIQ_WINDOW = 63                # ~3 months
SKIP = 21                      # the "-1": sessions between window end and today
WINDOWS = {'12': 252, '6': 126}
MAX_ABS_DAILY_LOGRET = 0.75    # a larger move implies an unadjusted split
CASH_VOL = 0.03                # below this annualized vol, a fund is a cash proxy
EDGE_CUT = 0.90                # lowest correlation the grouping UI can act on

DATA.mkdir(parents=True, exist_ok=True)


def require_key():
    if not API_KEY:
        raise SystemExit(
            'No API key. Export FMP_API_KEY (or API_KEY) with a Financial '
            'Modeling Prep key before running the fetch stages.')
    return API_KEY


def get(path, **params):
    """GET a JSON endpoint, retrying transient failures."""
    require_key()
    params['apikey'] = API_KEY
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{BASE}/{path}?{qs}'
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as e:                      # noqa: BLE001 - retry everything
            last = e
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f'{path} failed after 4 attempts: {last}')


def load(name):
    with open(DATA / name) as f:
        return json.load(f)


def save(name, obj):
    path = DATA / name
    with open(path, 'w') as f:
        json.dump(obj, f)
    return path


def bars_for(symbol, subdir, price_key='close'):
    """Ascending, complete bars for one symbol, with the in-progress session dropped."""
    path = DATA / subdir / f'{symbol}.json'
    if not path.exists():
        return []
    try:
        with open(path) as f:
            bars = json.load(f)
    except (ValueError, OSError):
        return []
    if not isinstance(bars, list):
        return []
    bars = [b for b in bars if b.get('date', '') < CUTOFF and b.get(price_key)]
    bars.sort(key=lambda b: b['date'])
    return bars
