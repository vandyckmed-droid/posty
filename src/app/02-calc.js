/* Pure calculations. Deterministic, DOM-free, independently testable --
   this is the layer to change when the analytics change. */
const Calc = (() => {

  /** Inverse-volatility weights normalised to 1. */
  function inverseVolWeights(rows) {
    const inv = rows.map(r => 1 / Math.max(r.v, 1e-6));
    const total = inv.reduce((a, b) => a + b, 0);
    return rows.map((r, i) => ({ ...r, w: total > 0 ? inv[i] / total : 0 }));
  }

  /** Largest-remainder rounding so displayed weights total exactly 100.0%. */
  function displayWeights(weights, dp = 1) {
    const f = 10 ** dp, target = 100 * f;
    const scaled = weights.map(w => w * 100 * f);
    const floors = scaled.map(Math.floor);
    let left = target - floors.reduce((a, b) => a + b, 0);
    const order = scaled.map((v, i) => [v - floors[i], i]).sort((a, b) => b[0] - a[0]);
    const out = floors.slice();
    for (let k = 0; k < order.length && left > 0; k++, left--) out[order[k][1]]++;
    return out.map(v => (v / f).toFixed(dp));
  }

  /** Per-sector count, share of names and share of weight, heaviest first. */
  function sectorExposure(held) {
    const n = held.length;
    if (!n) return [];
    const by = new Map();
    held.forEach(r => {
      const g = by.get(r.s) || { s: r.s, count: 0, weight: 0 };
      g.count++; g.weight += r.w; by.set(r.s, g);
    });
    return [...by.values()]
      .map(g => ({ ...g, names: g.count / n }))
      .sort((a, b) => b.weight - a.weight);
  }

  function median(xs) {
    if (!xs.length) return 0;
    const s = [...xs].sort((a, b) => a - b);
    return s[Math.floor(s.length / 2)];
  }

  /** Nearest nice number -- rounding up alone halves the gridline count. */
  function niceStep(span, target) {
    const raw = span / target;
    if (!(raw > 0) || !isFinite(raw)) return 0.01;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag)
      .reduce((a, c) => Math.abs(Math.log(c / raw)) < Math.abs(Math.log(a / raw)) ? c : a);
    return step > 0 ? step : 0.01;
  }

  /**
   * Rebase a shipped ratio series to 0% at the first session it trades in the
   * window. Series are integer ratios against each name's own first
   * observation, so q[t]/q[base] - 1 is exact for any window.
   */
  function rebase(series, from, to) {
    let base = null, start = from;
    for (let k = from; k <= to; k++) {
      if (series[k] != null) { base = series[k]; start = k; break; }
    }
    const pts = [];
    if (base != null) {
      for (let k = start; k <= to; k++) {
        if (series[k] != null) pts.push([k, series[k] / base - 1]);
      }
    }
    return pts;
  }

  /** Last observed value at or before session k. */
  function valueAt(pts, k) {
    let out = null;
    for (const [i, v] of pts) { if (i > k) break; out = v; }
    return out;
  }

  return { inverseVolWeights, displayWeights, sectorExposure, median, niceStep, rebase, valueAt };
})();
