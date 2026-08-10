/* Formatting only. No DOM, no state. */
const Fmt = (() => {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
  const sgn = (x, d = 1) => (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%";
  /* Return magnitudes here span +12% to +4000%, so precision adapts. */
  const ret = x => {
    const p = x * 100;
    return (p >= 0 ? "+" : "") + p.toFixed(Math.abs(p) >= 1000 ? 0 : 1) + "%";
  };
  const money = v => {
    if (v >= 1e9) return "$" + (v / 1e9).toFixed(v >= 1e10 ? 1 : 2) + "B";
    if (v >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
    return "$" + Math.round(v / 1e3) + "K";
  };
  const day = iso => new Date(iso + "T00:00:00Z")
    .toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  const shortDay = iso => new Date(iso + "T00:00:00Z")
    .toLocaleDateString(undefined, { month: "short", year: "2-digit", timeZone: "UTC" });
  return { esc, pct, sgn, ret, money, day, shortDay };
})();
