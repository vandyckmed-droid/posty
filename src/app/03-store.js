/* Dataset access, UI state, persistence and change notification. Views never
   reach past this into DATA, and never mutate state directly. */
const Store = (() => {
  const KEY = "momentum100.watchlist.v1";
  const SECTOR_COLOR = {
    "Technology":"var(--sec-tech)", "Communication Services":"var(--sec-comm)",
    "Consumer Cyclical":"var(--sec-cycl)", "Consumer Defensive":"var(--sec-def)",
    "Healthcare":"var(--sec-heal)", "Financial Services":"var(--sec-fin)",
    "Industrials":"var(--sec-ind)", "Energy":"var(--sec-ener)",
    "Basic Materials":"var(--sec-mat)", "Utilities":"var(--sec-util)",
    "Real Estate":"var(--sec-re)"
  };

  const ALL = DATA.rows;
  const BY_TICKER = new Map(ALL.map(r => [r.t, r]));

  const SORTS = [
    { k: "sc",  label: "Momentum score", dir: -1 },
    { k: "r",   label: "Rank",           dir:  1 },
    { k: "m12", label: "12-1 return",    dir: -1 },
    { k: "m6",  label: "6-1 return",     dir: -1 },
    { k: "i12", label: "12-1 IR",        dir: -1 },
    { k: "i6",  label: "6-1 IR",         dir: -1 },
    { k: "v",   label: "Volatility",     dir: -1 },
    { k: "dv",  label: "Dollar volume",  dir: -1 },
    { k: "t",   label: "Ticker",         dir:  1 },
    { k: "s",   label: "Sector",         dir:  1 }
  ];

  const state = {
    tab: "ranks",
    basis: "raw",
    sort: "sc", dir: -1,
    query: "", sectors: new Set(),
    holdSort: "w", group: false
  };

  const watch = (() => {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY));
      return new Set((Array.isArray(raw) ? raw : []).filter(t => BY_TICKER.has(t)));
    } catch { return new Set(); }
  })();
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify([...watch])); } catch {} };

  const listeners = new Set();
  const subscribe = fn => listeners.add(fn);
  const emit = () => listeners.forEach(fn => fn());

  /* Rows ship as the union of both bases' top 100; the active basis decides
     which 100 are ranked and what r / sc / p12 / p6 mean. */
  function applyBasis() { ALL.forEach(r => Object.assign(r, r[state.basis])); }
  applyBasis();

  const ranked = () => ALL.filter(r => r.r <= DATA.displaySize);

  function sectorCounts() {
    const c = {};
    ranked().forEach(r => { c[r.s] = (c[r.s] || 0) + 1; });
    return c;
  }

  /** Ranked rows after search and sector filters, in the active sort order. */
  function visible() {
    const q = state.query.trim().toLowerCase();
    const rows = ranked().filter(r => {
      if (state.sectors.size && !state.sectors.has(r.s)) return false;
      if (q && !(r.t.toLowerCase().includes(q) || r.n.toLowerCase().includes(q))) return false;
      return true;
    });
    const k = state.sort, d = state.dir;
    return rows.sort((a, b) => {
      const x = a[k], y = b[k];
      const c = typeof x === "string" ? x.localeCompare(y) : x - y;
      return c * d || a.r - b.r;
    });
  }

  /** Watchlist rows with inverse-volatility weights attached. */
  const held = () => Calc.inverseVolWeights([...watch].map(t => BY_TICKER.get(t)).filter(Boolean));

  function set(patch) {
    const basisChanged = patch.basis && patch.basis !== state.basis;
    Object.assign(state, patch);
    if (basisChanged) {
      applyBasis();
      const counts = sectorCounts();
      [...state.sectors].forEach(s => { if (!counts[s]) state.sectors.delete(s); });
      // an IR sort is meaningless outside the risk-adjusted basis
      if (state.basis !== "ra" && (state.sort === "i12" || state.sort === "i6")) {
        state.sort = "sc"; state.dir = -1;
      }
    }
    emit();
  }

  function toggleWatch(t) {
    if (watch.has(t)) watch.delete(t); else watch.add(t);
    persist();
    emit();
  }
  function clearWatch() { watch.clear(); persist(); emit(); }

  return {
    DATA, state, SORTS, subscribe, set, emit,
    row: t => BY_TICKER.get(t),
    all: () => ALL,
    ranked, visible, held, sectorCounts,
    watching: t => watch.has(t),
    watchCount: () => watch.size,
    toggleWatch, clearWatch,
    color: s => SECTOR_COLOR[s] || "var(--sec-none)",
    sortLabel: () => (SORTS.find(s => s.k === state.sort) || SORTS[0]).label
  };
})();
