/* Wiring: tab navigation, one delegated click handler, and re-render on change. */
const Main = (() => {
  const SCREENS = {
    ranks: { el: null, view: Ranks },
    watch: { el: null, view: Watchlist },
    about: { el: null, view: About }
  };

  function renderTab() {
    const tab = Store.state.tab;
    Object.entries(SCREENS).forEach(([k, s]) => {
      s.el.hidden = k !== tab;
      if (k === tab) s.view.render(s.el);
    });
    document.querySelectorAll(".tab").forEach(b =>
      b.dataset.tab === tab ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
    const n = Store.watchCount();
    const badge = document.getElementById("tabbadge");
    badge.hidden = n === 0;
    badge.textContent = n;
  }

  function go(tab) {
    if (Store.state.tab === tab) { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    Store.set({ tab });
    window.scrollTo({ top: 0 });
  }

  function init() {
    Object.keys(SCREENS).forEach(k => { SCREENS[k].el = document.getElementById("screen-" + k); });

    document.getElementById("stampdate").textContent = DATA.dataAsOf.slice(5).replace("-", "/") + " CLOSE";

    document.addEventListener("click", e => {
      const el = e.target.closest("[data-tab],[data-open],[data-toggle],[data-basis],[data-holdsort]," +
        "[data-tf],[data-drop],[data-add],[data-back],[data-sort],[data-sector],[data-flip]," +
        "[data-done],[data-allsectors],#cmp,#d-watch,#sortpill,#secpill,#groupbtn,#clearwatch,#qclear,#goranks,#stamp");
      if (!el) return;

      if (el.dataset.tab) { go(el.dataset.tab); return; }
      if (el.dataset.open) { Detail.open(el.dataset.open); return; }
      if (el.dataset.toggle) { Store.toggleWatch(el.dataset.toggle); return; }
      if (el.dataset.basis) { Store.set({ basis: el.dataset.basis }); return; }
      if (el.dataset.holdsort) { Store.set({ holdSort: el.dataset.holdsort }); return; }
      if (el.id === "sortpill") { Pickers.sort(); return; }
      if (el.id === "secpill") { Pickers.sectors(); return; }
      if (el.id === "groupbtn") { Store.set({ group: !Store.state.group }); return; }
      if (el.id === "clearwatch") { Store.clearWatch(); return; }
      if (el.id === "qclear") { Store.set({ query: "" }); return; }
      if (el.id === "goranks") { go("ranks"); return; }
      if (el.id === "stamp") { go("about"); return; }
      if (Detail.handle(el)) return;
      Pickers.handle(el);
    });

    /* Search re-renders the list, so the field is restored and refocused. */
    document.addEventListener("input", e => {
      if (e.target.id !== "q") return;
      const pos = e.target.selectionStart;
      Store.set({ query: e.target.value });
      const next = document.getElementById("q");
      if (next) { next.focus(); try { next.setSelectionRange(pos, pos); } catch {} }
    });

    Store.subscribe(() => {
      renderTab();
      Detail.refresh();
    });
    renderTab();
  }

  return { init };
})();
