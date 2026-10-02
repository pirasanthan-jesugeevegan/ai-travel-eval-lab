"""Static CSS and JS for the HTML report (kept out of the renderer for readability)."""

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10);
  --series: #2a78d6; --good: #0ca30c; --good-text: #006300; --bad: #d03b3b;
  --wash: rgba(11,11,11,0.04);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --series: #3987e5; --good-text: #0ca30c;
    --wash: rgba(255,255,255,0.05);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19;
  --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
  --series: #3987e5; --good-text: #0ca30c; --wash: rgba(255,255,255,0.05);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 32px 0 4px; }
.sub, .note { color: var(--ink-2); margin: 0 0 12px; }
.note { font-size: 12px; color: var(--muted); }
.verdict { display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: var(--surface); border: 1px solid var(--ring); border-radius: 8px;
  padding: 14px 16px; margin: 16px 0; }
.verdict .big { font-size: 22px; font-weight: 600; }
.pass { color: var(--good-text); } .fail { color: var(--bad); }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.tile { background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 12px 14px; }
.tile .label { color: var(--ink-2); font-size: 12px; }
.tile .value { font-size: 28px; font-weight: 600; margin: 2px 0; }
.tile .status, .tile .delta { font-size: 12px; }
.delta.up { color: var(--good-text); } .delta.down { color: var(--bad); } .delta.flat { color: var(--muted); }
.panels { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.panel { margin: 0; background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 10px 10px 4px; position: relative; }
.panel figcaption { display: flex; justify-content: space-between; padding: 0 4px; font-size: 13px; }
.panel svg { width: 100%; height: auto; display: block; }
svg text { fill: var(--muted); font-size: 10px; font-family: inherit; }
svg .grid { stroke: var(--grid); stroke-width: 1; }
svg .axis { stroke: var(--axis); stroke-width: 1; }
svg .thr { stroke: var(--muted); stroke-width: 1; }
svg .chg { stroke: var(--axis); stroke-width: 1; }
svg .line { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
svg .dot { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
svg .dot.below { fill: var(--bad); }
svg .endlabel { fill: var(--ink); font-size: 11px; font-weight: 600; }
svg .xhair { stroke: var(--ink-2); stroke-width: 1; visibility: hidden; }
svg .hit { fill: transparent; outline: none; cursor: default; }
svg .hit:focus-visible { fill: var(--wash); }
.legend { font-size: 12px; color: var(--ink-2); margin: 4px 0 8px; }
.legend .diamond { color: var(--bad); }
.tablewrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th { color: var(--ink-2); font-weight: 600; position: sticky; top: 0; background: var(--surface); }
td.num { font-variant-numeric: tabular-nums; }
td.chg { font-weight: 700; }
td.wrap { white-space: normal; min-width: 220px; }
tr:last-child td { border-bottom: 0; }
.cell { text-align: center; cursor: default; }
.cell.ok { color: var(--good-text); } .cell.bad { color: var(--bad); font-weight: 700; }
.cell:focus-visible { outline: 2px solid var(--ink-2); outline-offset: -2px; }
details { margin-top: 8px; } summary { cursor: pointer; color: var(--ink-2); font-size: 12px; }
#tip { position: fixed; z-index: 10; pointer-events: none; display: none; max-width: 300px;
  background: var(--surface); color: var(--ink); border: 1px solid var(--axis); border-radius: 6px;
  padding: 8px 10px; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.18); }
#tip .t-title { color: var(--ink-2); } #tip .t-value { font-size: 15px; font-weight: 600; margin: 2px 0; }
#tip .t-line { color: var(--ink-2); }
.box { background: var(--surface); border: 1px solid var(--ring); border-radius: 8px; padding: 10px 14px; margin: 12px 0; }
.box ol { margin: 8px 0 4px; padding-left: 20px; } .box li { margin: 4px 0; color: var(--ink-2); }
.note-box { color: var(--ink-2); }
.summary { font-size: 15px; margin: 12px 0 16px; }
.badge { font-size: 10px; color: var(--ink-2); border: 1px solid var(--axis); border-radius: 4px; padding: 0 4px; margin-left: 4px; }
.todo { font-weight: 600; color: var(--ink-2); border: 1px dashed var(--axis); border-radius: 4px; padding: 0 6px; }
@media (max-width: 480px) { .verdict .big { font-size: 18px; } }
"""

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
