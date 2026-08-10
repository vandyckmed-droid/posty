/* Sort and sector choosers. Both are bottom sheets so the options land under
   the thumb instead of in a menu anchored to the top of the screen. */
const Pickers = (() => {
  const CHECK = '<svg viewBox="0 0 24 24" stroke-width="3.2"><path d="M20 6L9 17l-5-5"/></svg>';

  function sort() {
    const st = Store.state;
    const opts = Store.SORTS.filter(o => st.basis === "ra" || (o.k !== "i12" && o.k !== "i6"));
    Sheet.show(`
      <div class="sheet-title" id="sheet-title">Sort by</div>
      <div class="optlist" role="listbox">
        ${opts.map(o => `<button class="opt" role="option" data-sort="${o.k}"
            aria-selected="${st.sort === o.k}">
            <span class="nm">${o.label}</span>
            <span class="cnt">${st.sort === o.k ? (st.dir === 1 ? "ascending" : "descending") : ""}</span>
            <span class="chk">${CHECK}</span></button>`).join("")}
      </div>
      <div class="sheet-actions">
        <button class="btn" data-flip="1">Reverse order</button>
        <button class="btn primary" data-done="1">Done</button>
      </div>`);
  }

  function sectors() {
    const st = Store.state, counts = Store.sectorCounts();
    const list = Object.keys(counts).sort();
    Sheet.show(`
      <div class="sheet-title" id="sheet-title">Sectors</div>
      <div class="optlist">
        ${list.map(s => `<button class="opt" data-sector="${Fmt.esc(s)}"
            aria-checked="${st.sectors.has(s)}" role="checkbox">
            <span class="dotc" style="--sc:${Store.color(s)}"></span>
            <span class="nm">${Fmt.esc(s)}</span>
            <span class="cnt">${counts[s]}</span>
            <span class="chk">${CHECK}</span></button>`).join("")}
      </div>
      <div class="sheet-actions">
        <button class="btn" data-allsectors="1">All</button>
        <button class="btn primary" data-done="1">Done</button>
      </div>`);
  }

  function handle(el) {
    if (el.dataset.sort) {
      const k = el.dataset.sort, st = Store.state;
      const def = Store.SORTS.find(o => o.k === k);
      Store.set(st.sort === k ? { dir: -st.dir } : { sort: k, dir: def.dir });
      sort();
      return true;
    }
    if (el.dataset.flip) { Store.set({ dir: -Store.state.dir }); sort(); return true; }
    if (el.dataset.sector) {
      const s = el.dataset.sector, set = Store.state.sectors;
      if (set.has(s)) set.delete(s); else set.add(s);
      Store.emit();
      sectors();
      return true;
    }
    if (el.dataset.allsectors) { Store.state.sectors.clear(); Store.emit(); sectors(); return true; }
    if (el.dataset.done) { Sheet.close(); return true; }
    return false;
  }

  return { sort, sectors, handle };
})();
