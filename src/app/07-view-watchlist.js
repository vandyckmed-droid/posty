/* Watchlist: hold a basket and see what it is made of. */
const Watchlist = (() => {
  const X = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  function holdCard(r, shownWeight) {
    return `<div class="hold" style="--sc:${Store.color(r.s)};--w:${(r.w * 100).toFixed(2)}%">
      <span class="bar"></span>
      <button data-open="${r.t}" aria-label="Open ${Fmt.esc(r.t)} detail"
        style="position:absolute;inset:0;border-radius:var(--r)"></button>
      <div class="idline"><span class="tk">${Fmt.esc(r.t)}</span></div>
      <div class="co trunc">${Fmt.esc(r.n)}</div>
      <div class="meta trunc"><i></i>${Fmt.esc(r.s)} · #${r.r} · sc ${r.sc.toFixed(1)} · &#963; ${Fmt.pct(r.v)}</div>
      <div class="wt">${shownWeight}%<span class="wtl">weight</span></div>
      <button class="rm" data-toggle="${r.t}" aria-label="Remove ${Fmt.esc(r.t)} from watchlist">${X}</button>
    </div>`;
  }

  function exposure(held) {
    const agg = Calc.sectorExposure(held);
    return `<div class="section-h"><h2>Sector exposure</h2></div>
    <div class="card" style="padding:14px">
      <div class="expbar" aria-hidden="true">${agg.map(g =>
        `<span style="--sc:${Store.color(g.s)};flex:${g.weight.toFixed(5)} 0 0"></span>`).join("")}</div>
      ${agg.map(g => `<div class="exprow" style="--sc:${Store.color(g.s)}">
        <div class="top"><i></i><span class="nm">${Fmt.esc(g.s)}</span>
          <span class="ct">${g.count} ${g.count === 1 ? "stock" : "stocks"}</span>
          <span class="pw">${Fmt.pct(g.weight)}</span></div>
        <div class="track names"><b style="width:${(g.names * 100).toFixed(2)}%"></b></div>
        <div class="track weight"><b style="width:${(g.weight * 100).toFixed(2)}%"></b></div>
        <div class="legend"><span>${Fmt.pct(g.names)} of names</span><span>${Fmt.pct(g.weight)} of weight</span></div>
      </div>`).join("")}
    </div>`;
  }

  function render(host) {
    const held = Store.held();
    const n = held.length;
    if (!n) {
      host.innerHTML = `<div class="section-h"><h2>Watchlist</h2></div>
        <div class="card empty">
          No names yet.<br>Add stocks from <b style="color:var(--neon)">Ranks</b> to build an
          inverse-volatility basket.
          <div style="margin-top:16px"><button class="btn primary" id="goranks" style="max-width:200px;margin:0 auto">Browse ranks</button></div>
        </div>`;
      return;
    }

    const wtdVol = held.reduce((a, r) => a + r.w * r.v, 0);
    const avgScore = held.reduce((a, r) => a + r.sc, 0) / n;
    const sectors = new Set(held.map(r => r.s)).size;

    // Rounded once across the whole book so grouping never re-scales a weight.
    const order = { w: (a, b) => b.w - a.w, r: (a, b) => a.r - b.r,
                    t: (a, b) => a.t.localeCompare(b.t), s: (a, b) => a.s.localeCompare(b.s) || b.w - a.w };
    const shown = new Map();
    Calc.displayWeights(held.map(h => h.w)).forEach((w, i) => shown.set(held[i].t, w));

    let body;
    if (Store.state.group) {
      const groups = Calc.sectorExposure(held).map(g => ({
        ...g, items: held.filter(h => h.s === g.s).sort((a, b) => b.w - a.w)
      }));
      body = groups.map(g => `
        <div class="grp" style="--sc:${Store.color(g.s)}"><i></i>${Fmt.esc(g.s)}
          <span class="gw">${Fmt.pct(g.weight)}</span></div>
        <div class="list">${g.items.map(r => holdCard(r, shown.get(r.t))).join("")}</div>`).join("");
    } else {
      body = `<div class="list">${[...held].sort(order[Store.state.holdSort])
        .map(r => holdCard(r, shown.get(r.t))).join("")}</div>`;
    }

    host.innerHTML = `
      <div class="section-h"><h2>Portfolio</h2>
        <span class="aside">${n} ${n === 1 ? "name" : "names"}</span></div>
      <div class="statgrid">
        <div class="stat volt"><span class="lbl">Wtd avg vol</span><span class="v">${Fmt.pct(wtdVol)}</span></div>
        <div class="stat"><span class="lbl">Avg score</span><span class="v">${avgScore.toFixed(1)}</span></div>
        <div class="stat"><span class="lbl">Sectors</span><span class="v">${sectors}</span></div>
      </div>
      <div class="card total" style="margin-top:8px"><span>Total weight</span><b>100.0%</b></div>

      <div class="section-h"><h2>Holdings</h2></div>
      <div class="railbar" style="margin-bottom:8px">
        <div class="seg" role="group" aria-label="Sort holdings">
          ${[["w","Weight"],["r","Rank"],["t","Ticker"],["s","Sector"]].map(([k, l]) =>
            `<button data-holdsort="${k}" aria-pressed="${Store.state.holdSort === k}">${l}</button>`).join("")}
        </div>
        <button class="pill" id="groupbtn" data-active="${Store.state.group}">
          <svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>Group by sector</button>
        <button class="pill" id="clearwatch">
          <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>Clear</button>
      </div>
      ${body}
      ${exposure(held)}`;
  }

  return { render };
})();
