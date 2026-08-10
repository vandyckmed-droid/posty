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
EDGE_CUT = 0.90                # lowest raw correlation the grouping UI can act on
RESID_CUT = 0.85               # same, on market-adjusted (PC1-removed) correlation

# A curated run pins the universe to an explicit list and skips discovery and the
# liquidity screen entirely: the list IS the universe. Liquidity is still measured
# and displayed, it just stops being a gate.
UNIVERSE_FILE = os.environ.get('ETF_UNIVERSE')
COMBINED_WEIGHTS = {'12': 0.5, '6': 0.5}   # hardwired blend of the two windows


def curated_universe():
    """[(ticker, category, label)] from ETF_UNIVERSE, or None for a discovery run."""
    if not UNIVERSE_FILE:
        return None
    rows = []
    with open(UNIVERSE_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            rows.append((parts[0], parts[1] if len(parts) > 1 else '',
                         parts[2] if len(parts) > 2 else ''))
    return rows

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


# Buckets that are definitively not a basket of shares. "Real Estate (Listed/REITs)"
# deliberately absent: a REIT fund holds listed equities and belongs with the stocks.
NON_EQUITY = ('fixed income', 'fixed-income', 'bond', 'commodit', 'gold', 'alternativ',
              'multi-asset', 'multi-sector', 'cash', 'high yield', 'loans', 'municipal',
              'government', 'investment grade', 'asset allocation', 'real assets')
# Sector labels the vendor uses for anything that is not an operating company.
NOT_A_SECTOR = ('cash & others', 'other', 'others', 'cash', 'n/a', '')


def _load(sym, suffix='', subdir='profile'):
    path = DATA / subdir / f'{sym}{suffix}.json'
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text() or 'null')
    except (ValueError, OSError):
        return None
    return data or None


def profile(sym):
    """Cost, size and composition from stage 4. Absent fields simply do not render."""
    data = _load(sym)
    if not data:
        return {}
    p = data[0]
    out = {}
    if p.get('expenseRatio') is not None:
        out['er'] = round(float(p['expenseRatio']), 3)
    if p.get('assetsUnderManagement'):
        out['aum'] = round(float(p['assetsUnderManagement']))
    if p.get('holdingsCount') is not None:
        out['hc'] = int(p['holdingsCount'])
    for key, field in (('iss', 'etfCompany'), ('ac', 'assetClass')):
        if p.get(field):
            out[key] = str(p[field])

    sectors = [(str(x.get('industry') or ''), float(x.get('exposure') or 0))
               for x in (p.get('sectorsList') or [])]
    sectors = [(nm, ex) for nm, ex in sectors if ex > 0]
    sectors.sort(key=lambda x: -x[1])
    if sectors:
        out['sec'] = [[nm, round(ex, 1)] for nm, ex in sectors[:6]]

    countries = []
    for x in (_load(sym, '.country') or []):
        pctstr = str(x.get('weightPercentage') or '').rstrip('%')
        try:
            pct = float(pctstr)
        except ValueError:
            continue
        if pct > 0:
            countries.append((str(x.get('country') or ''), pct))
    countries.sort(key=lambda x: -x[1])
    if countries:
        out['cty'] = [[nm, round(pct, 1)] for nm, pct in countries[:4]]

    # Is this a basket of shares? The sector mix is the reliable signal -- the vendor
    # labels SPDR Gold Shares "Equity", but reports it as 100% Cash & Others. Where
    # sector data is missing entirely, fall back to the asset class alone.
    ac = (out.get('ac') or '').lower()
    if any(k in ac for k in NON_EQUITY):
        out['stk'] = False
    elif sectors:
        total = sum(ex for _, ex in sectors)
        real = sum(ex for nm, ex in sectors if nm.strip().lower() not in NOT_A_SECTOR)
        out['stk'] = bool(total) and (real / total) >= 0.60
    else:
        out['stk'] = any(k in ac for k in ('equity', 'stock', 'growth', 'real estate'))
    return out


def holdings(sym):
    """Top company positions from stage 5 (SEC N-PORT).

    Filtered to operating companies (assetCat "EC"). A fund's single largest line is
    often a cash sweep or an affiliated pooled vehicle -- XBI's biggest position is a
    State Street cash fund at 8% -- which is normal but answers no question about what
    the fund is betting on. The share of the fund actually held in shares is reported
    separately instead of being silently dropped.
    """
    data = _load(sym, subdir='holdings')
    if not data or data.get('err') or not data.get('top'):
        return {}
    top = [[p.get('t') or '', p.get('n') or '', p.get('p') or 0.0]
           for p in data['top'] if (p.get('p') or 0) > 0 and p.get('eq')]
    if not top:
        return {}
    return {
        'hAsOf': data.get('asOf'),
        'hN': data.get('total'),
        'hEq': data.get('eqPct'),
        'hTop': top[:12],
        'hConc': round(sum(x[2] for x in top[:10]), 1),   # weight of the top ten
    }
