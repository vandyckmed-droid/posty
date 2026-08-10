/* The one bottom-sheet host. Views hand it markup and a mount callback; it owns
   presentation, swipe-to-dismiss, focus and scroll locking. */
const Sheet = (() => {
  const el = document.getElementById("sheet");
  const inner = document.getElementById("sheet-inner");
  const scrim = document.getElementById("scrim");
  const grabber = document.getElementById("grabber");
  let restore = null, onClose = null, open = false;

  function show(html, opts = {}) {
    inner.innerHTML = html;
    el.classList.toggle("tall", !!opts.tall);
    el.setAttribute("aria-labelledby", opts.labelledBy || "sheet-title");
    if (!open) {
      restore = document.activeElement;
      scrim.hidden = false; el.hidden = false;
      document.body.style.overflow = "hidden";
      open = true;
    }
    el.style.transform = "";
    inner.scrollTop = 0;
    onClose = opts.onClose || null;
    if (opts.mount) opts.mount(inner);
    (inner.querySelector("[data-autofocus]") || grabber).focus({ preventScroll: true });
  }

  function close() {
    if (!open) return;
    open = false;
    scrim.hidden = true; el.hidden = true;
    el.style.transform = "";
    document.body.style.overflow = "";
    inner.innerHTML = "";
    const cb = onClose; onClose = null;
    if (cb) cb();
    if (restore && document.contains(restore)) restore.focus({ preventScroll: true });
  }

  /* Drag the grabber down to dismiss -- the gesture a phone user expects. */
  let y0 = null;
  grabber.addEventListener("pointerdown", e => {
    y0 = e.clientY;
    try { grabber.setPointerCapture(e.pointerId); } catch {}
  });
  grabber.addEventListener("pointermove", e => {
    if (y0 == null) return;
    const dy = Math.max(0, e.clientY - y0);
    el.style.transform = `translate(-50%, ${dy}px)`;
  });
  const end = e => {
    if (y0 == null) return;
    const dy = Math.max(0, e.clientY - y0);
    y0 = null;
    if (dy > 90) close(); else el.style.transform = "";
  };
  grabber.addEventListener("pointerup", end);
  grabber.addEventListener("pointercancel", () => { y0 = null; el.style.transform = ""; });
  grabber.addEventListener("click", close);
  scrim.addEventListener("click", close);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && open) close(); });

  el.addEventListener("keydown", e => {
    if (e.key !== "Tab") return;
    const f = [...el.querySelectorAll('button:not([disabled]),input,[tabindex]:not([tabindex="-1"])')]
      .filter(n => n.offsetParent !== null);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  return { show, close, isOpen: () => open, body: () => inner };
})();
