/* Canvas total-return chart plus its crosshair. Owns no app state: the caller
   passes what to draw and where the crosshair is. */
const Chart = (() => {
  const CAL = DATA.calendar;
  const LINE = ["#00F5A0", "#00D2FF", "#C08BFF", "#FFB86B"];
  const TF = { "3M": 63, "6M": 126, "1Y": 252, "2Y": CAL.length };
  const PAD = { l: 4, r: 48, t: 12, b: 22 };

  const windowStart = tf => Math.max(0, CAL.length - 1 - (TF[tf] || TF["1Y"]));

  /** Each ticker rebased to 0% at the window start, in draw order. */
  function tracks(tickers, tf) {
    const s0 = windowStart(tf), s1 = CAL.length - 1;
    return tickers.filter(Boolean).map((t, i) => ({
      t, color: LINE[i], primary: i === 0, pts: Calc.rebase(DATA.series[t], s0, s1)
    })).filter(s => s.pts.length > 1);
  }

  function draw(canvas, ts, tf, hover) {
    const ctx = canvas.getContext("2d");
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!ts.length) return;

    const s0 = windowStart(tf), s1 = CAL.length - 1;
    const X = k => PAD.l + ((k - s0) / Math.max(s1 - s0, 1)) * (w - PAD.l - PAD.r);

    /* Domain hugs the data with 0% always in view; gridlines land on nice
       values inside it. Snapping the domain to the step would let a series
       dipping a hair below zero drag the floor down a whole gridline. */
    let lo = 0, hi = 0;
    ts.forEach(s => s.pts.forEach(([, v]) => { if (v < lo) lo = v; if (v > hi) hi = v; }));
    if (hi === lo) { hi += 0.01; lo -= 0.01; }
    const p = (hi - lo) * 0.06; lo -= p; hi += p;
    const step = Calc.niceStep(hi - lo, 4);
    const Y = v => PAD.t + (1 - (v - lo) / (hi - lo)) * (h - PAD.t - PAD.b);

    ctx.font = '10px ui-monospace,"SF Mono",Menlo,monospace';
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
      if (Math.abs(v) < 1e-9) continue;               // 0% is drawn on its own
      const y = Math.round(Y(v)) + .5;
      ctx.beginPath();
      ctx.setLineDash([2, 4]);
      ctx.strokeStyle = "rgba(154,168,165,.10)";
      ctx.lineWidth = 1;
      ctx.moveTo(PAD.l, y); ctx.lineTo(w - PAD.r, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#66756F";
      ctx.fillText((v > 0 ? "+" : "") + Math.round(v * 100) + "%", w - PAD.r + 7, y);
    }
    const yz = Math.round(Y(0)) + .5;
    ctx.beginPath();
    ctx.strokeStyle = "rgba(154,168,165,.34)";
    ctx.lineWidth = 1;
    ctx.moveTo(PAD.l, yz); ctx.lineTo(w - PAD.r, yz); ctx.stroke();
    ctx.fillStyle = "#9AA8A5";
    ctx.fillText("0%", w - PAD.r + 7, yz);

    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#66756F";
    for (let i = 0; i < 4; i++) {
      const k = Math.round(s0 + ((s1 - s0) * (i + .5)) / 4);
      ctx.fillText(Fmt.shortDay(CAL[k]), X(k), h - 6);
    }

    if (ts.length === 1) {                            // soft fill only when alone
      const s = ts[0], g = ctx.createLinearGradient(0, PAD.t, 0, h - PAD.b);
      const up = s.pts[s.pts.length - 1][1] >= 0;
      g.addColorStop(0, up ? "rgba(0,245,160,.16)" : "rgba(255,84,112,.16)");
      g.addColorStop(1, "rgba(0,245,160,0)");
      ctx.beginPath();
      s.pts.forEach(([k, v], i) => i ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v)));
      ctx.lineTo(X(s.pts[s.pts.length - 1][0]), Y(0));
      ctx.lineTo(X(s.pts[0][0]), Y(0));
      ctx.closePath();
      ctx.fillStyle = g;
      ctx.fill();
    }

    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ts.forEach(s => {
      ctx.beginPath();
      s.pts.forEach(([k, v], i) => i ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v)));
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.primary ? 2.1 : 1.6;          // a touch heavier for phone
      ctx.globalAlpha = s.primary ? 1 : .92;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    if (hover != null) {
      const x = Math.round(X(hover)) + .5;
      ctx.beginPath();
      ctx.strokeStyle = "rgba(236,242,239,.3)";
      ctx.lineWidth = 1;
      ctx.moveTo(x, PAD.t); ctx.lineTo(x, h - PAD.b); ctx.stroke();
      ts.forEach(s => {
        const v = Calc.valueAt(s.pts, hover);
        if (v == null) return;
        ctx.beginPath();
        ctx.arc(x, Y(v), 4, 0, Math.PI * 2);
        ctx.fillStyle = s.color; ctx.fill();
        ctx.strokeStyle = "#0E1113"; ctx.lineWidth = 1.8; ctx.stroke();
      });
    } else {
      ts.forEach(s => {
        const [k, v] = s.pts[s.pts.length - 1];
        ctx.beginPath();
        ctx.arc(X(k), Y(v), s.primary ? 3.4 : 2.8, 0, Math.PI * 2);
        ctx.fillStyle = s.color; ctx.fill();
      });
    }
  }

  /** Map a pointer x to the nearest session index. */
  function sessionAt(canvas, clientX, tf) {
    const box = canvas.getBoundingClientRect();
    const s0 = windowStart(tf), s1 = CAL.length - 1;
    const frac = (clientX - box.left - PAD.l) / Math.max(box.width - PAD.l - PAD.r, 1);
    return Math.max(s0, Math.min(s1, Math.round(s0 + frac * (s1 - s0))));
  }

  /** Inline SVG sparkline for list rows. */
  function sparkline(pts, id, w = 54, h = 22) {
    const lo = Math.min(...pts), hi = Math.max(...pts), span = hi - lo || 1;
    const X = i => (i / (pts.length - 1)) * (w - 2) + 1;
    const Y = v => h - 2 - ((v - lo) / span) * (h - 4);
    const d = pts.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ");
    const c = pts[pts.length - 1] >= pts[0] ? "var(--neon)" : "var(--down)";
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <defs><linearGradient id="sg${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${c}" stop-opacity=".3"/><stop offset="1" stop-color="${c}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${d} L${X(pts.length - 1).toFixed(1)} ${h} L${X(0).toFixed(1)} ${h} Z" fill="url(#sg${id})" stroke="none"/>
      <path d="${d}" fill="none" stroke="${c}" stroke-width="1.3"/>
    </svg>`;
  }

  return { LINE, TF, tracks, draw, sessionAt, sparkline, calendar: CAL };
})();
