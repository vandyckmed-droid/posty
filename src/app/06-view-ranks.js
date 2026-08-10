/* Ranks: find stocks. A scannable card list, with search, sort and sector
   filters on one thumb rail. */
const Ranks = (() => {
  const CHECK = '<svg viewBox="0 0 24 24" stroke-width="3.2"><path d="M20 6L9 17l-5-5"/></svg>';
  const PLUS  = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';

  function controls() {
    const st = Store.state, counts = Store.sectorCounts();
    const nSec = st.sectors.size;
    return `
    <div class="controls">
      <label class="searchbar">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
        <input id="q" type="search" inputmode="search" placeholder="Search ticker or company"
               autocomplete="off" aria-label="Search ticker or company" value="${Fmt.esc(st.query)}">
        ${st.query ? `<button class="clear" id="qclear" aria-label="Clear search">
          <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>` : ""}
      </label>
      <div class="railwrap"><div class="railbar">
        <div class="seg" role="group" aria-label="Ranking basis">
          <button data-basis="raw" aria-pressed="${st.basis === "raw"}">Raw</button>
          <button data-basis="ra" aria-pressed="${st.basis === "ra"}">Risk-adj</button>
        </div>
        <button class="pill" id="sortpill" data-active="${st.sort !== "sc"}">
          <svg viewBox="0 0 24 24"><path d="M7 4v16M7 20l-3-3M17 20V4M17 4l3 3"/></svg>
          ${Fmt.esc(Store.sortLabel())}
        </button>
        <button class="pill" id="secpill" data-active="${nSec > 0}">
          <svg viewBox="0 0 24 24"><path d="M3 5h18M6 12h12M10 19h4"/></svg>
          ${nSec ? `${nSec} sector${nSec > 1 ? "s" : ""}` : "All sectors"}
          <span class="cnt">${Store.ranked().length}</span>
        </button>
      </div></div>
    </div>`;
  }

  function summary() {
    const shown = Store.ranked();
    const med = Calc.median(shown.map(r => r.m12));
    const share = DATA.displaySize / DATA.universeSize * 100;
    return `<div class="statgrid">
      <div class="stat"><span class="lbl">Universe</span><span class="v">${DATA.universeSize.toLocaleString()}</span></div>
      <div class="stat accent"><span class="lbl">Shown</span><span class="v">${DATA.displaySize}<span class="mut" style="font-size:11px"> · top ${share < 10 ? share.toFixed(1) : Math.round(share)}%</span></span></div>
      <div class="stat"><span class="lbl">Median 12-1</span><span class="v up">${Fmt.ret(med)}</span></div>
    </div>`;
  }

  /* One metric per row: 12-1 by default, or whatever the list is sorted by, so
     the active sort is always visible without widening the row. */
  const METRIC = {
    m12: r => ["12-1", Fmt.ret(r.m12), r.m12 >= 0],
    m6:  r => ["6-1",  Fmt.ret(r.m6),  r.m6 >= 0],
    i12: r => ["12-1 IR", r.i12.toFixed(2), r.i12 >= 0],
    i6:  r => ["6-1 IR",  r.i6.toFixed(2),  r.i6 >= 0],
    v:   r => ["Vol", Fmt.pct(r.v), null],
    dv:  r => ["ADDV", Fmt.money(r.dv), null]
  };

  function row(r) {
    const on = Store.watching(r.t);
    const [key, val, good] = (METRIC[Store.state.sort] || METRIC.m12)(r);
    const tone = good === null ? "" : good ? "up" : "dn";
    return `<div class="row ${on ? "on" : ""}" style="--sc:${Store.color(r.s)}">
      <button class="rowtap" data-open="${r.t}" aria-label="Open ${Fmt.esc(r.t)} detail"></button>
      <div class="idline"><span class="rk">#${r.r}</span><span class="tk">${Fmt.esc(r.t)}</span></div>
      <div class="co trunc">${Fmt.esc(r.n)}</div>
      <div class="meta">
        <span class="sec trunc"><i></i>${Fmt.esc(r.s)}</span>
        <span class="ret ${tone}"><span class="k">${key}</span><b>${val}</b></span>
      </div>
      <div class="scorebox">
        <span class="score" style="color:${on ? "var(--neon)" : "var(--ink)"}">${r.sc.toFixed(1)}</span>
        <span class="scorelbl">score</span>
      </div>
      ${Chart.sparkline(r.sp, r.t)}
      <button class="watch" data-toggle="${r.t}" aria-pressed="${on}"
        aria-label="${on ? "Remove" : "Add"} ${Fmt.esc(r.t)} ${on ? "from" : "to"} watchlist"><i>${on ? CHECK : PLUS}</i></button>
    </div>`;
  }

  function render(host) {
    const rows = Store.visible();
    const total = Store.ranked().length;
    host.innerHTML = controls() + summary() +
      `<div class="section-h"><h2>Momentum leaders</h2>
        <span class="aside">${rows.length === total ? `${total} names` : `${rows.length} of ${total}`}</span></div>` +
      (rows.length
        ? `<div class="list">${rows.map(row).join("")}</div>`
        : `<div class="card empty">Nothing matches these filters.<br>Try clearing the sector filter or search.</div>`);
  }

  return { render };
})();
