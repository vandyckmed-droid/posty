/* Ticker detail: understand one stock, and compare it with up to three others.
   Lives in the sheet host; the compare picker pushes and pops within the same
   sheet rather than stacking a second surface over it. */
const Detail = (() => {
  const MAX = 4;
  const TFS = ["3M", "6M", "1Y", "2Y"];
  const st = { t: null, compare: [], tf: "1Y", hover: null };
  let canvas = null;

  const rows = () => [st.t, ...st.compare];
  const tracks = () => Chart.tracks(rows(), st.tf);

  function readoutHTML() {
    const ts = tracks(), k = st.hover;
    return ts.map(s => {
      const v = k != null ? Calc.valueAt(s.pts, k) : s.pts[s.pts.length - 1][1];
      return `<span class="ro" style="--c:${s.color}"><i></i><span class="t">${Fmt.esc(s.t)}</span>
        <span class="r ${v >= 0 ? "up" : "dn"}">${v == null ? "—" : Fmt.ret(v)}</span>
        ${s.primary ? "" : `<button class="x" data-drop="${Fmt.esc(s.t)}" aria-label="Remove ${Fmt.esc(s.t)} from chart">
          <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`}</span>`;
    }).join("") +
    `<span class="ro-date">${k != null ? Fmt.day(Chart.calendar[k]) : st.tf + " total return"}</span>`;
  }

  function paint() {
    const ro = document.getElementById("readout");
    if (ro) ro.innerHTML = readoutHTML();
    if (canvas) Chart.draw(canvas, tracks(), st.tf, st.hover);
  }

  function html() {
    const r = Store.row(st.t);
    const on = Store.watching(r.t);
    const icon = on
      ? '<svg viewBox="0 0 24 24" stroke-width="3.2"><path d="M20 6L9 17l-5-5"/></svg>'
      : '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';
    return `
      <div class="sheet-h">
        <div class="who">
          <h2 id="sheet-title">${Fmt.esc(r.t)}</h2>
          <p class="sub trunc">${Fmt.esc(r.n)} · <span class="sec" style="--sc:${Store.color(r.s)}"><i></i>${Fmt.esc(r.s)}</span></p>
        </div>
        <button class="iconbtn" id="d-watch" aria-pressed="${on}"
          aria-label="${on ? "Remove" : "Add"} ${Fmt.esc(r.t)} ${on ? "from" : "to"} watchlist"><i>${icon}</i></button>
      </div>
      <div class="quad">
        <div><span class="lbl">Rank</span><span class="v">#${r.r}</span></div>
        <div><span class="lbl">12-1</span><span class="v ${r.m12 >= 0 ? "up" : "dn"}">${Fmt.ret(r.m12)}</span></div>
        <div><span class="lbl">6-1</span><span class="v ${r.m6 >= 0 ? "up" : "dn"}">${Fmt.ret(r.m6)}</span></div>
        <div><span class="lbl">Vol</span><span class="v">${Fmt.pct(r.v)}</span></div>
      </div>
      <div class="readout" id="readout"></div>
      <div class="chartwrap"><canvas id="chart"></canvas></div>
      <div class="chart-foot">
        <div class="seg" role="group" aria-label="Chart timeframe">
          ${TFS.map(f => `<button data-tf="${f}" aria-pressed="${st.tf === f}">${f}</button>`).join("")}
        </div>
        <button class="pill" id="cmp" ${st.compare.length >= MAX - 1 ? "disabled" : ""}>
          <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>Compare</button>
      </div>
      <p class="note">Cumulative total return from dividend-adjusted closes, each line rebased to
        0% at the start of the window. Drag across the chart to read any date.</p>`;
  }

  function mount(root) {
    canvas = root.querySelector("#chart");
    paint();
    new ResizeObserver(() => paint()).observe(canvas);

    let tracking = false;
    canvas.addEventListener("pointerdown", e => {
      tracking = true;
      try { canvas.setPointerCapture(e.pointerId); } catch {}   // pointer may already be gone
      st.hover = Chart.sessionAt(canvas, e.clientX, st.tf);
      paint();
    });
    canvas.addEventListener("pointermove", e => {
      if (!tracking && e.pointerType !== "mouse") return;
      st.hover = Chart.sessionAt(canvas, e.clientX, st.tf);
      paint();
    });
    const stop = () => { tracking = false; st.hover = null; paint(); };
    canvas.addEventListener("pointerup", stop);
    canvas.addEventListener("pointercancel", stop);
    canvas.addEventListener("pointerleave", () => { if (!tracking) stop(); });
  }

  function show() {
    Sheet.show(html(), { tall: true, mount, onClose: () => { canvas = null; } });
  }

  function open(t) {
    if (!Store.row(t) || !DATA.series[t]) return;
    st.t = t; st.compare = []; st.tf = "1Y"; st.hover = null;
    show();
  }

  /* Compare picker, pushed into the same sheet. */
  function picker(query = "") {
    const taken = new Set(rows());
    const q = query.trim().toLowerCase();
    const opts = Store.all().filter(r => !taken.has(r.t) && DATA.series[r.t] &&
      (!q || r.t.toLowerCase().includes(q) || r.n.toLowerCase().includes(q))).slice(0, 80);
    Sheet.show(`
      <div class="sheet-title" id="sheet-title">Compare with</div>
      <label class="searchbar" style="margin-bottom:10px">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
        <input id="cmpq" type="search" placeholder="Search the ranked list" autocomplete="off"
               value="${Fmt.esc(query)}" aria-label="Search stocks to compare">
      </label>
      <div class="optlist">${opts.length ? opts.map(r => `
        <button class="opt" data-add="${r.t}">
          <span class="dotc" style="--sc:${Store.color(r.s)}"></span>
          <span class="tk">${Fmt.esc(r.t)}</span>
          <span class="nm trunc mut">${Fmt.esc(r.n)}</span>
          <span class="cnt">#${r.r}</span>
        </button>`).join("") : `<div class="empty">No match in the ranked list.</div>`}</div>
      <div class="sheet-actions"><button class="btn" data-back="1">Back to ${Fmt.esc(st.t)}</button></div>`,
      { tall: true });
    const input = Sheet.body().querySelector("#cmpq");
    input.addEventListener("input", () => {
      const v = input.value, pos = input.selectionStart;
      picker(v);
      const next = Sheet.body().querySelector("#cmpq");
      next.focus(); try { next.setSelectionRange(pos, pos); } catch {}
    });
  }

  function handle(el) {
    if (el.dataset.tf) { st.tf = el.dataset.tf; st.hover = null; show(); return true; }
    if (el.dataset.drop) { st.compare = st.compare.filter(t => t !== el.dataset.drop); show(); return true; }
    if (el.id === "cmp") { picker(); return true; }
    if (el.dataset.add) {
      if (st.compare.length < MAX - 1) st.compare.push(el.dataset.add);
      show(); return true;
    }
    if (el.dataset.back) { show(); return true; }
    if (el.id === "d-watch") { Store.toggleWatch(st.t); show(); return true; }
    return false;
  }

  return { open, handle, current: () => st.t, refresh: () => { if (st.t && Sheet.isOpen()) paint(); } };
})();
