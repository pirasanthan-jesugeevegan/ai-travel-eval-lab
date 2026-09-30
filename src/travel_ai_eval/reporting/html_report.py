"""Self-contained HTML trend report (inline SVG + a little JS, no external assets).

Built from reports/history.jsonl. Each gated metric gets its own small chart with the
threshold drawn on it (one axis per chart, never dual-axis), diamonds mark runs
below threshold, and hairlines mark where the model / prompt / dataset version changed.
Every chart has a table-view twin further down the page.
"""

import sys
from pathlib import Path

from travel_ai_eval.config import REPORTS_DIR
from travel_ai_eval.models.results import RunResult
from travel_ai_eval.reporting.history import (
    HISTORY_PATH,
    HistoryEntry,
    changes_vs_previous,
    load_history,
)
from travel_ai_eval.reporting.html_assets import CSS, JS
from travel_ai_eval.reporting.html_common import (
    PANELS,
    Panel,
    esc,
    fmt,
    metric_value,
    run_lines,
    tip_attr,
    when,
)
from travel_ai_eval.reporting.html_tables import (
    render_configs,
    render_failures,
    render_matrix,
    render_runs_table,
)

HTML_PATH = REPORTS_DIR / "report.html"
LATEST_PATH = REPORTS_DIR / "latest.json"
_EPS = 1e-9

# chart geometry (SVG user units)
W, H, LEFT, RIGHT, TOP, BOTTOM = 320, 150, 34, 46, 14, 28
PW, PH = W - LEFT - RIGHT, H - TOP - BOTTOM


def _threshold(entries: list[HistoryEntry], gate: str | None) -> float | None:
    if gate is None or not entries:
        return None
    return next((c.threshold for c in entries[-1].gate.checks if c.name == gate), None)


def _range(values: list[float], is_rate: bool) -> tuple[float, float]:
    low = min(values)
    if is_rate:
        lo = max(0.0, int((low - 0.05) * 20) / 20)
        return (lo if lo < 0.95 else 0.9), 1.0
    lo = max(1.0, int((low - 0.2) * 2) / 2)
    return (lo if lo < 4.5 else 4.0), 5.0


def render_panel(p: Panel, entries: list[HistoryEntry], changes: list[list[str]]) -> str:
    n = len(entries)
    thr = _threshold(entries, p.gate)
    vals = [v for e in entries if (v := metric_value(e, p.attr)) is not None]
    if not vals:
        return f'<figure class="panel"><figcaption><b>{esc(p.label)}</b></figcaption><p class="note">No data.</p></figure>'
    lo, hi = _range(vals + ([thr] if thr is not None else []), p.is_rate)

    def x(i: int) -> float:
        return LEFT + (PW * i / (n - 1) if n > 1 else PW / 2)

    def y(v: float) -> float:
        return TOP + PH * (1 - (v - lo) / (hi - lo))

    step = PW / (n - 1) if n > 1 else PW
    out = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(p.label)} across {n} runs">'
    ]
    for t in (lo, (lo + hi) / 2, hi):
        out.append(f'<line class="grid" x1="{LEFT}" x2="{LEFT + PW}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        label = f"{t * 100:.0f}%" if p.is_rate else f"{t:.1f}"
        out.append(f'<text x="{LEFT - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{label}</text>')
    out.append(f'<line class="axis" x1="{LEFT}" x2="{LEFT + PW}" y1="{y(lo):.1f}" y2="{y(lo):.1f}"/>')
    for i in range(1, n):
        if changes[i]:
            cx = x(i) - step / 2
            out.append(f'<line class="chg" x1="{cx:.1f}" x2="{cx:.1f}" y1="{TOP}" y2="{TOP + PH}"/>')
    if thr is not None and lo <= thr <= hi:
        label = f"min {thr * 100:.0f}%" if p.is_rate else f"min {thr:g}"
        out.append(f'<line class="thr" x1="{LEFT}" x2="{LEFT + PW}" y1="{y(thr):.1f}" y2="{y(thr):.1f}"/>')
        out.append(f'<text x="{LEFT + 2}" y="{y(thr) - 3:.1f}">{label}</text>')

    pts = [(i, v) for i, e in enumerate(entries) if (v := metric_value(e, p.attr)) is not None]
    if len(pts) > 1:
        path = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in pts)
        out.append(f'<polyline class="line" points="{path}"/>')
    for i, v in pts:
        cx, cy = x(i), y(v)
        if thr is not None and v < thr - _EPS:
            d = f"{cx:.1f},{cy - 6:.1f} {cx + 6:.1f},{cy:.1f} {cx:.1f},{cy + 6:.1f} {cx - 6:.1f},{cy:.1f}"
            out.append(f'<polygon class="dot below" points="{d}"/>')
        else:
            out.append(f'<circle class="dot" cx="{cx:.1f}" cy="{cy:.1f}" r="4"/>')
    last_i, last_v = pts[-1]
    out.append(
        f'<text class="endlabel" x="{x(last_i) + 8:.1f}" y="{y(last_v) + 4:.1f}">{fmt(last_v, p.is_rate)}</text>'
    )
    out.append(f'<text x="{LEFT}" y="{H - 8}">{esc(when(entries[0].metadata.timestamp))}</text>')
    if n > 1:
        out.append(
            f'<text x="{LEFT + PW}" y="{H - 8}" text-anchor="end">{esc(when(entries[-1].metadata.timestamp))}</text>'
        )
    out.append(f'<line class="xhair" x1="0" x2="0" y1="{TOP}" y2="{TOP + PH}"/>')
    for i, e in enumerate(entries):
        v = metric_value(e, p.attr)
        title = f"Run #{i + 1} · {when(e.metadata.timestamp)}"
        tip = tip_attr(title, f"{p.label}: {fmt(v, p.is_rate)}", run_lines(e, changes[i]))
        out.append(
            f'<rect class="hit" tabindex="0" data-x="{x(i):.1f}" data-tip="{tip}" '
            f'x="{x(i) - step / 2:.1f}" y="{TOP}" width="{step:.1f}" height="{PH}"/>'
        )
    out.append("</svg>")
    latest = fmt(metric_value(entries[-1], p.attr), p.is_rate)
    return (
        f'<figure class="panel"><figcaption><b>{esc(p.label)}</b><span>{latest}</span></figcaption>'
        + "".join(out)
        + "</figure>"
    )


def render_tiles(entries: list[HistoryEntry]) -> str:
    latest = entries[-1]
    prev = entries[-2] if len(entries) > 1 else None
    checks = {c.name: c for c in latest.gate.checks}
    tiles = []
    for p in PANELS:
        if p.gate is None or p.gate not in checks:
            continue
        c = checks[p.gate]
        v = metric_value(latest, p.attr)
        status = (
            '<span class="pass">✓ PASS</span>' if c.passed else '<span class="fail">✕ FAIL</span>'
        )
        req = f"≥ {c.threshold * 100:.0f}%" if p.is_rate else f"≥ {c.threshold:g}"
        delta = '<span class="delta flat">first recorded run</span>'
        pv = metric_value(prev, p.attr) if prev else None
        if v is not None and pv is not None:
            d = v - pv
            unit = d * 100 if p.is_rate else d
            text = f"{unit:+.1f} pts" if p.is_rate else f"{unit:+.2f}"
            if abs(d) < (0.0005 if p.is_rate else 0.005):
                delta = '<span class="delta flat">— no change vs previous run</span>'
            elif d > 0:
                delta = f'<span class="delta up">▲ {text} vs previous run</span>'
            else:
                delta = f'<span class="delta down">▼ {text} vs previous run</span>'
        tiles.append(
            f'<div class="tile"><div class="label">{esc(p.label)}</div>'
            f'<div class="value">{fmt(v, p.is_rate)}</div>'
            f'<div class="status">{status} · required {req}</div><div>{delta}</div></div>'
        )
    return f'<div class="tiles">{"".join(tiles)}</div>'


def render_html(entries: list[HistoryEntry], latest: RunResult | None = None) -> str:
    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Travel AI Eval Trends</title><style>{CSS}</style></head><body><main>"
    )
    tail = f'</main><div id="tip" role="tooltip"></div><script>{JS}</script></body></html>'
    if not entries:
        body = (
            "<h1>Travel AI evaluation</h1><p class='sub'>No runs recorded yet. Run "
            "<code>uv run python -m travel_ai_eval.evaluation.runner</code> to create the first entry.</p>"
        )
        return head + body + tail

    changes = changes_vs_previous(entries)
    last = entries[-1]
    m = last.metadata
    verdict = (
        '<span class="big pass">✓ QUALITY GATE: PASS</span>'
        if last.gate.passed
        else '<span class="big fail">✕ QUALITY GATE: FAIL</span>'
    )
    failed = [c for c in last.gate.checks if not c.passed]
    why = (
        "Below threshold: " + ", ".join(esc(c.name.replace("_", " ")) for c in failed) if failed else "All thresholds met."
    )
    body = [
        "<h1>Travel AI evaluation: trends</h1>",
        f"<p class='sub'>{len(entries)} recorded run(s). Newest first in the tables; oldest to newest in the charts.</p>",
        f"<div class='verdict'>{verdict}<span>{why}</span>"
        f"<span class='note'>Run #{len(entries)} · {esc(when(m.timestamp))} UTC · {esc(m.model)} · "
        f"prompt {esc(m.prompt_version)} · dataset {esc(m.dataset_version)} · {m.total_cases} cases"
        f"{' · ' + esc(last.label) if last.label else ''}</span></div>",
        render_tiles(entries),
        "<h2>Trends</h2>",
        "<p class='sub'>One chart per metric, each on its own scale, with the required threshold drawn on it. "
        "Vertical hairlines mark a change of model, prompt or dataset version between two runs.</p>",
        '<p class="legend">● at or above threshold · <span class="diamond">◆</span> below threshold · hover or focus a run for details</p>',
        f'<div class="panels">{"".join(render_panel(p, entries, changes) for p in PANELS)}</div>',
        "<h2>What changed, run by run</h2>",
        render_runs_table(entries, changes),
        "<h2>Results by configuration</h2>",
        render_configs(entries),
        "<h2>Case stability</h2>",
        render_matrix(entries, changes),
    ]
    if latest is not None:
        body += [f"<h2>Failures in the latest full run ({esc(when(latest.metadata.timestamp))})</h2>", render_failures(latest)]
    return head + "".join(body) + tail


def write_html_report(
    history_path: Path = HISTORY_PATH, latest_path: Path = LATEST_PATH, out: Path = HTML_PATH
) -> Path:
    latest = None
    if latest_path.is_file():
        try:
            latest = RunResult.model_validate_json(latest_path.read_text(encoding="utf-8"))
        except ValueError:
            latest = None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(load_history(history_path), latest), encoding="utf-8")
    return out


def main() -> int:
    print(write_html_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
