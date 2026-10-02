"""Static CSS and JS for the HTML report (kept out of the renderer for readability).

Design: the quality gate is rendered as an airport gate sign (the one bold element); everything
else is quiet. System fonts only so the report stays a single self-contained file.
"""

_LIGHT = """
  color-scheme: light;
  --page: #f3f3f7; --surface: #ffffff; --ink: #252734; --ink-2: #4d5066; --muted: #686c83;
  --line: #e4e5ee; --line-2: #cfd1de; --wash: rgba(37,39,52,0.05);
  --series: #3b6fd4; --series-wash: rgba(59,111,212,0.13);
  --good: #0ca30c; --good-text: #006300; --good-bg: #e6f5e6;
  --bad: #d03b3b; --bad-text: #b42323; --bad-bg: #fdeaea; --bad-wash: rgba(208,59,59,0.055);
  --sign: #252734; --sign-2: #3b3e55; --amber: #ffc35b; --sign-ink: #f5f6fa; --sign-muted: #a9adc4;
  --shadow: 0 1px 2px rgba(37,39,52,0.06), 0 10px 28px -14px rgba(37,39,52,0.22);
  --glow: radial-gradient(900px 420px at 88% -8%, rgba(255,195,91,0.20), transparent 62%),
          radial-gradient(700px 400px at -6% 0%, rgba(59,111,212,0.08), transparent 60%);
"""
_DARK = """
  color-scheme: dark;
  --page: #1c1e29; --surface: #252734; --ink: #f2f3f8; --ink-2: #c0c3d4; --muted: #9094ab;
  --line: #343749; --line-2: #45495f; --wash: rgba(255,255,255,0.05);
  --series: #7aa7ff; --series-wash: rgba(122,167,255,0.18);
  --good: #0ca30c; --good-text: #3fd13f; --good-bg: rgba(12,163,12,0.16);
  --bad: #e25b5b; --bad-text: #ff8b8b; --bad-bg: rgba(226,91,91,0.16); --bad-wash: rgba(226,91,91,0.1);
  --sign: #1b1d28; --sign-2: #363950; --amber: #ffc35b; --sign-ink: #f5f6fa; --sign-muted: #a0a4bb;
  --shadow: 0 1px 2px rgba(0,0,0,0.4), 0 10px 28px -14px rgba(0,0,0,0.65);
  --glow: radial-gradient(900px 440px at 88% -10%, rgba(255,195,91,0.13), transparent 62%),
          radial-gradient(700px 420px at -6% 0%, rgba(122,167,255,0.10), transparent 60%);
"""

CSS = (
    ":root {" + _LIGHT + """
  --ui: "Avenir Next", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
  --display: "Bahnschrift", "DIN Condensed", "Barlow Condensed", "Arial Narrow", "Helvetica Neue", system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) {""" + _DARK + """} }
:root[data-theme="dark"] {""" + _DARK + """}
""" + """
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body { margin: 0; background: var(--glow), var(--page); background-attachment: fixed; color: var(--ink); font: 15px/1.55 var(--ui); }
main { max-width: 1160px; margin: 0 auto; padding: 8px 20px 72px; }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--series); outline-offset: 2px; }

/* top bar */
.top { position: sticky; top: 0; z-index: 5; background: color-mix(in srgb, var(--page) 88%, transparent);
  backdrop-filter: blur(10px); border-bottom: 1px solid var(--line); }
.bar { max-width: 1160px; margin: 0 auto; padding: 10px 20px; display: flex; gap: 20px; align-items: center; }
.brand { font-weight: 700; letter-spacing: 0.01em; margin-right: auto; display: flex; align-items: center; gap: 9px; }
.brand::before { content: ""; width: 11px; height: 11px; border-radius: 3px; background: var(--amber); box-shadow: 0 0 0 3px rgba(255,195,91,0.25); }
.bar nav { display: flex; gap: 4px; flex-wrap: wrap; }
.bar nav a { text-decoration: none; color: var(--ink-2); font-size: 13px; padding: 4px 10px; border-radius: 999px; }
.bar nav a:hover { background: var(--wash); color: var(--ink); box-shadow: inset 0 -2px 0 var(--amber); }

/* hero: gate sign + key numbers */
.hero { display: grid; grid-template-columns: minmax(280px, 0.9fr) 1.5fr; gap: 16px; margin-top: 22px; align-items: stretch; }
.sign { background: linear-gradient(160deg, var(--sign-2), var(--sign) 60%); color: var(--sign-ink);
  border-radius: 18px; padding: 22px 24px; box-shadow: inset 0 3px 0 var(--amber), var(--shadow); display: flex; flex-direction: column; gap: 14px; }
.sign-top { display: flex; justify-content: space-between; align-items: baseline; color: var(--amber);
  font-family: var(--display); font-size: 19px; letter-spacing: 0.04em; }
.sign-top .run { color: var(--sign-muted); font-size: 15px; letter-spacing: 0.02em; }
.sign-status { display: flex; align-items: center; gap: 16px; }
.light { width: 18px; height: 18px; border-radius: 50%; flex: none; background: #3fd13f; box-shadow: 0 0 0 4px rgba(63,209,63,0.22), 0 0 18px rgba(63,209,63,0.6); }
.sign.bad .light { background: #ff5d5d; box-shadow: 0 0 0 4px rgba(255,93,93,0.25), 0 0 18px rgba(255,93,93,0.6); }
.status-word { font-family: var(--display); font-size: 76px; line-height: 0.95; font-weight: 700; letter-spacing: 0.01em; }
.sign-why { margin: 0; color: var(--sign-muted); font-size: 14px; max-width: 34ch; }
.sign-meta { margin: auto 0 0; display: grid; grid-template-columns: auto 1fr; gap: 3px 14px; font-size: 13px;
  border-top: 1px solid rgba(255,255,255,0.14); padding-top: 12px; }
.sign-meta dt { color: var(--sign-muted); } .sign-meta dd { margin: 0; overflow-wrap: anywhere; }

.keys { list-style: none; margin: 0; padding: 6px 4px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 18px; box-shadow: var(--shadow); display: flex; flex-direction: column; }
.key { display: grid; grid-template-columns: minmax(130px, 1.2fr) 92px minmax(84px, auto) minmax(120px, 1fr);
  gap: 14px; align-items: center; padding: 11px 16px; border-bottom: 1px solid var(--line); }
.key:last-child { border-bottom: 0; }
.k-name { font-weight: 600; font-size: 14px; }
.badge { display: inline-block; font-size: 11px; font-weight: 500; color: var(--ink-2); background: var(--wash);
  border-radius: 6px; padding: 1px 7px; margin-left: 6px; white-space: nowrap; }
.spark { width: 92px; height: 30px; display: block; }
.spark .l { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.spark .d { fill: var(--amber); stroke: var(--surface); stroke-width: 2; }
.spark .d.below { fill: var(--bad); }
.k-val { font-family: var(--display); font-size: 34px; font-weight: 700; line-height: 1; text-align: right; }
.k-meta { display: flex; flex-direction: column; gap: 3px; align-items: flex-start; font-size: 12px; }
.chip { display: inline-flex; gap: 5px; align-items: center; border-radius: 999px; padding: 1px 9px; font-weight: 600; font-size: 12px; }
.chip.pass { background: var(--good-bg); color: var(--good-text); }
.chip.fail { background: var(--bad-bg); color: var(--bad-text); }
.pass { color: var(--good-text); } .fail { color: var(--bad-text); }
.delta { font-size: 12px; } .delta.up { color: var(--good-text); } .delta.down { color: var(--bad-text); } .delta.flat { color: var(--muted); }

.lede { font-size: 17px; max-width: 74ch; margin: 22px 0 6px; color: var(--ink); }
.help { margin: 6px 0 0; font-size: 13px; color: var(--ink-2); }
.help summary { cursor: pointer; color: var(--ink-2); }
.help ol { margin: 8px 0 0; padding-left: 20px; max-width: 80ch; } .help li { margin: 4px 0; }

/* sections */
section.block { margin-top: 44px; }
.block > h2 { font-size: 20px; margin: 0 0 4px; letter-spacing: -0.005em; }
.cap { margin: 0 0 14px; color: var(--ink-2); max-width: 78ch; }
.note { color: var(--muted); font-size: 12px; margin: 8px 0 0; }
.legend { font-size: 12px; color: var(--ink-2); margin: 0 0 10px; }
.legend .diamond { color: var(--bad); } .legend .now { color: var(--amber); text-shadow: 0 0 0 var(--ink-2); }

/* trend charts */
.panels { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 14px; }
.panel { margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 14px 14px 6px; position: relative; box-shadow: var(--shadow); }
.panel-head { display: flex; justify-content: space-between; align-items: baseline; padding: 0 4px 2px; }
.p-title { font-weight: 600; font-size: 14px; }
.p-val { font-family: var(--display); font-size: 28px; font-weight: 700; line-height: 1; }
.panel svg { width: 100%; height: auto; display: block; }
svg text { fill: var(--muted); font-size: 10px; font-family: var(--ui); }
svg .grid { stroke: var(--line); stroke-width: 1; }
svg .axis { stroke: var(--line-2); stroke-width: 1; }
svg .thr { stroke: var(--ink-2); stroke-width: 1; opacity: 0.55; }
svg .zone { fill: var(--bad-wash); }
svg .chg { stroke: var(--line-2); stroke-width: 1; }
svg .line { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
svg .dot { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
svg .dot.now { fill: var(--amber); stroke: var(--surface); }
svg .ring { fill: none; stroke: var(--amber); stroke-width: 1.5; opacity: 0.55; }
svg .dot.below { fill: var(--bad); }
svg .xhair { stroke: var(--ink-2); stroke-width: 1; visibility: hidden; }
svg .hit { fill: transparent; outline: none; cursor: default; }
svg .hit:focus-visible { fill: var(--wash); }

/* category meters */
.cats { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; box-shadow: var(--shadow); }
.cat { display: grid; grid-template-columns: minmax(280px, 1.6fr) 1.4fr 64px minmax(120px, 0.7fr); gap: 18px; align-items: center; padding: 9px 18px; border-bottom: 1px solid var(--line); }
.cat:last-child { border-bottom: 0; }
.cat b { text-transform: capitalize; display: block; }
.cat small { color: var(--muted); font-size: 12px; }
.meter { height: 8px; border-radius: 99px; background: var(--wash); overflow: hidden; display: flex; }
.meter { position: relative; } .meter i { display: block; background: var(--series); } .meter i.miss { background: var(--bad); }
.meter .req { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--ink); opacity: 0.7; }
.cat .n { font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }

/* tables */
.tablewrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; box-shadow: var(--shadow); }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 9px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; font-size: 12px; position: sticky; top: 0; background: var(--surface); white-space: nowrap; }
tbody tr:hover { background: var(--wash); }
tr.latest td:first-child { box-shadow: inset 4px 0 0 var(--amber); } tr.latest { background: color-mix(in srgb, var(--amber) 9%, transparent); } tr:last-child td { border-bottom: 0; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
th:nth-child(2), td:nth-child(2) { white-space: nowrap; }
td.wrap { min-width: 220px; }
.cfg { display: grid; gap: 1px; font-size: 12px; color: var(--ink-2); white-space: nowrap; }
.cfg span.chg, .chg-chip { background: var(--series-wash); color: var(--ink); border-radius: 6px; padding: 0 6px; font-weight: 600; width: fit-content; }
.chg-chip { display: inline-block; margin: 2px 4px 0 0; font-size: 12px; }
.run-no { font-family: var(--display); font-size: 20px; font-weight: 700; }
.mini-meter { display: grid; gap: 4px; min-width: 120px; } .mini-meter .meter { height: 6px; }

/* case matrix */
.cell { text-align: center; width: 44px; padding: 6px; }
.cell span { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 8px; font-size: 13px; font-weight: 700; }
.cell.ok span { background: var(--good-bg); color: var(--good-text); }
.cell.bad span { background: var(--bad-bg); color: var(--bad-text); }
.cell.none span { color: var(--muted); font-weight: 400; }
.cell:focus-visible { outline: 2px solid var(--series); outline-offset: -2px; }

/* collapsible reference sections */
details.fold { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; margin-top: 12px; box-shadow: var(--shadow); }
details.fold > summary { cursor: pointer; padding: 14px 18px; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
details.fold > summary::-webkit-details-marker { display: none; }
details.fold > summary::after { content: "+"; color: var(--muted); font-size: 18px; line-height: 1; }
details.fold[open] > summary::after { content: "–"; }
details.fold > summary small { font-weight: 400; color: var(--muted); margin-left: 8px; }
details.fold > .inner { padding: 0 18px 16px; }
details.fold .tablewrap { box-shadow: none; }
.todo { font-weight: 600; color: var(--ink-2); border: 1px dashed var(--line-2); border-radius: 6px; padding: 0 7px; font-size: 12px; }
.empty { background: var(--surface); border: 1px dashed var(--line-2); border-radius: 14px; padding: 14px 18px; color: var(--ink-2); }
footer { margin-top: 48px; color: var(--muted); font-size: 12px; }

#tip { position: fixed; z-index: 10; pointer-events: none; display: none; max-width: 300px; background: var(--surface); color: var(--ink);
  border: 1px solid var(--line-2); border-radius: 10px; padding: 9px 12px; font-size: 12px; box-shadow: 0 8px 28px rgba(0,0,0,0.25); }
#tip .t-title { color: var(--ink-2); } #tip .t-value { font-size: 15px; font-weight: 600; margin: 2px 0; } #tip .t-line { color: var(--ink-2); }

@media (max-width: 860px) {
  .hero { grid-template-columns: 1fr; }
  .key { grid-template-columns: 1fr auto; row-gap: 6px; } .key .spark { display: none; }
  .k-meta { grid-column: 1 / -1; flex-direction: row; gap: 10px; align-items: center; }
  .cat { grid-template-columns: 1fr auto; } .cat .meter { grid-column: 1 / -1; order: 3; } .cat .st { display: none; }
  .status-word { font-size: 60px; }
}
"""
)

JS = """
(function () {
  var tip = document.getElementById('tip');
  function row(cls, text) {
    var d = document.createElement('div'); d.className = cls; d.textContent = text; return d;
  }
  function show(el) {
    var data; try { data = JSON.parse(el.getAttribute('data-tip')); } catch (e) { return; }
    tip.replaceChildren(row('t-title', data.title), row('t-value', data.value));
    (data.lines || []).forEach(function (l) { tip.appendChild(row('t-line', l)); });
    tip.style.display = 'block';
    var r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    var y = r.top - h - 8; if (y < 8) y = r.bottom + 8;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
    var svg = el.closest('svg');
    if (svg && el.hasAttribute('data-x')) {
      var xh = svg.querySelector('.xhair');
      xh.setAttribute('x1', el.getAttribute('data-x')); xh.setAttribute('x2', el.getAttribute('data-x'));
      xh.style.visibility = 'visible';
    }
  }
  function hide(el) {
    tip.style.display = 'none';
    var svg = el.closest && el.closest('svg');
    if (svg) { var xh = svg.querySelector('.xhair'); if (xh) xh.style.visibility = 'hidden'; }
  }
  document.addEventListener('pointerover', function (e) { var t = e.target.closest('[data-tip]'); if (t) show(t); });
  document.addEventListener('pointerout', function (e) { var t = e.target.closest('[data-tip]'); if (t) hide(t); });
  document.addEventListener('focusin', function (e) { var t = e.target.closest('[data-tip]'); if (t) show(t); });
  document.addEventListener('focusout', function (e) { var t = e.target.closest('[data-tip]'); if (t) hide(t); });
})();
"""
