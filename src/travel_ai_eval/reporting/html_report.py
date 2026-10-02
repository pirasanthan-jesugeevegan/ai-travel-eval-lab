"""Self-contained HTML trend report (inline SVG + a little JS, no external assets).

Built from reports/history.jsonl. Each gated metric gets its own small chart with the
threshold drawn on it (one axis per chart, never dual-axis), diamonds mark runs
below threshold, and hairlines mark where the model / prompt / dataset version changed.
Every chart has a table-view twin further down the page.
"""

import sys
from pathlib import Path

from travel_ai_eval.config import HISTORY_PATH, HTML_PATH, LATEST_PATH
from travel_ai_eval.models.results import RunResult
from travel_ai_eval.reporting.history import (
    HistoryEntry,
    changes_vs_previous,
    load_history,
)
from travel_ai_eval.reporting.html_assets import CSS, JS
from travel_ai_eval.reporting.html_common import (
    PANELS,
    esc,
    fmt,
    metric_value,
    run_lines,
    tip_attr,
    when,
)
from travel_ai_eval.reporting.html_sections import (
    fold,
    intro,
    render_categories,
    render_gate_table,
    render_glossary,
    render_how_to_read,
    render_not_measured,
    render_single_run_note,
    render_summary,
)
from travel_ai_eval.reporting.html_tables import (
    render_configs,
    render_failures,
    render_matrix,
    render_runs_table,
)
from travel_ai_eval.reporting.metrics import Metric

_EPS = 1e-9

# chart geometry (SVG user units)
W, H, LEFT, RIGHT, TOP, BOTTOM = 320, 160, 34, 14, 12, 26
PW, PH = W - LEFT - RIGHT, H - TOP - BOTTOM
SPARK_RUNS = 12


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


def render_panel(p: Metric, entries: list[HistoryEntry], changes: list[list[str]]) -> str:
    n = len(entries)
    thr = _threshold(entries, p.gate)
    vals = [v for e in entries if (v := metric_value(e, p.attr)) is not None]
    head = (
        f'<div class="panel-head"><span class="p-title">{esc(p.label)}'
        f'<span class="badge">{esc(p.kind)}</span></span>'
    )
    if not vals:
        return f'<figure class="panel">{head}</div><p class="note">No data.</p></figure>'
    lo, hi = _range(vals + ([thr] if thr is not None else []), p.is_rate)

    def x(i: int) -> float:
        return LEFT + (PW * i / (n - 1) if n > 1 else PW / 2)

    def y(v: float) -> float:
        return TOP + PH * (1 - (v - lo) / (hi - lo))

    step = PW / (n - 1) if n > 1 else PW
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(p.label)} across {n} runs">']
    if thr is not None and lo <= thr <= hi:  # shaded "below the required level" zone
        out.append(
            f'<rect class="zone" x="{LEFT}" y="{y(thr):.1f}" width="{PW}" height="{y(lo) - y(thr):.1f}"/>'
        )
    for t in (lo, (lo + hi) / 2, hi):
        out.append(f'<line class="grid" x1="{LEFT}" x2="{LEFT + PW}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        label = f"{t * 100:.0f}%" if p.is_rate else f"{t:.1f}"
        out.append(f'<text x="{LEFT - 6}" y="{y(t) + 3:.1f}" text-anchor="end">{label}</text>')
    for i in range(1, n):
        if changes[i]:
            cx = x(i) - step / 2
            out.append(f'<line class="chg" x1="{cx:.1f}" x2="{cx:.1f}" y1="{TOP}" y2="{TOP + PH}"/>')
    if thr is not None and lo <= thr <= hi:
        label = f"required {thr * 100:.0f}%" if p.is_rate else f"required {thr:g}"
        out.append(f'<line class="thr" x1="{LEFT}" x2="{LEFT + PW}" y1="{y(thr):.1f}" y2="{y(thr):.1f}"/>')
        # A threshold at the very top of the chart gets its label below the line, clear of the points.
        label_y = y(thr) + 12 if thr >= hi - _EPS else y(thr) - 4
        out.append(f'<text x="{LEFT + PW}" y="{label_y:.1f}" text-anchor="end">{label}</text>')

    pts = [(i, v) for i, e in enumerate(entries) if (v := metric_value(e, p.attr)) is not None]
    if len(pts) > 1:
        path = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in pts)
        out.append(f'<polyline class="line" points="{path}"/>')
    for i, v in pts:
        cx, cy = x(i), y(v)
        if thr is not None and v < thr - _EPS:
            d = f"{cx:.1f},{cy - 6.5:.1f} {cx + 6.5:.1f},{cy:.1f} {cx:.1f},{cy + 6.5:.1f} {cx - 6.5:.1f},{cy:.1f}"
            out.append(f'<polygon class="dot below" points="{d}"/>')
        elif i == pts[-1][0]:  # the current run: gold, with a halo
            out.append(f'<circle class="ring" cx="{cx:.1f}" cy="{cy:.1f}" r="8.5"/>')
            out.append(f'<circle class="dot now" cx="{cx:.1f}" cy="{cy:.1f}" r="5"/>')
        else:
            out.append(f'<circle class="dot" cx="{cx:.1f}" cy="{cy:.1f}" r="4"/>')
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
    return f'<figure class="panel">{head}<span class="p-val">{latest}</span></div>' + "".join(out) + "</figure>"


def _sparkline(values: list[float], below_last: bool) -> str:
    """Tiny trend line for a key-number row: the last SPARK_RUNS runs on the metric's own scale."""
    vals = values[-SPARK_RUNS:]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    xs = [4 + (84 * i / (len(vals) - 1) if len(vals) > 1 else 42) for i in range(len(vals))]
    ys = [26 - 22 * ((v - lo) / span) if hi > lo else 15 for v in vals]
    line = ""
    if len(vals) > 1:
        line = '<polyline class="l" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys, strict=True)) + '"/>'
    cls = "d below" if below_last else "d"
    return (
        f'<svg class="spark" viewBox="0 0 92 30" role="img" aria-label="last {len(vals)} runs">'
        f'{line}<circle class="{cls}" cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4"/></svg>'
    )


def _delta_html(p: Metric, v: float | None, pv: float | None) -> str:
    if v is None or pv is None:
        return '<span class="delta flat">first recorded run</span>'
    d = v - pv
    unit = d * 100 if p.is_rate else d
    text = f"{unit:+.1f} pts" if p.is_rate else f"{unit:+.2f}"
    if abs(d) < (0.0005 if p.is_rate else 0.005):
        return '<span class="delta flat">no change vs previous run</span>'
    if d > 0:
        return f'<span class="delta up">▲ {text} vs previous run</span>'
    return f'<span class="delta down">▼ {text} vs previous run</span>'


def render_keys(entries: list[HistoryEntry]) -> str:
    latest = entries[-1]
    prev = entries[-2] if len(entries) > 1 else None
    checks = {c.name: c for c in latest.gate.checks}
    rows = []
    for p in PANELS:
        if p.gate is None or p.gate not in checks:
            continue
        c = checks[p.gate]
        v = metric_value(latest, p.attr)
        series = [x for e in entries if (x := metric_value(e, p.attr)) is not None]
        req = f"{c.threshold * 100:.0f}%" if p.is_rate else f"{c.threshold:g}"
        chip = (
            f'<span class="chip pass">✓ PASS, min {req}</span>'
            if c.passed
            else f'<span class="chip fail">✕ FAIL, min {req}</span>'
        )
        rows.append(
            f'<li class="key" title="{esc(p.meaning)}">'
            f'<div class="k-name">{esc(p.label)}<span class="badge">{esc(p.kind)}</span></div>'
            f"{_sparkline(series, not c.passed)}"
            f'<div class="k-val">{fmt(v, p.is_rate)}</div>'
            f'<div class="k-meta">{chip}{_delta_html(p, v, metric_value(prev, p.attr) if prev else None)}</div></li>'
        )
    return f'<ul class="keys" aria-label="Key numbers for the latest run">{"".join(rows)}</ul>'


def render_sign(entries: list[HistoryEntry]) -> str:
    last = entries[-1]
    m = last.metadata
    ok = last.gate.passed
    failed = [c.name.replace("_", " ") for c in last.gate.checks if not c.passed]
    why = "All thresholds met." if ok else "Below threshold: " + ", ".join(failed)
    word, icon = ("PASS", "✓") if ok else ("FAIL", "✕")
    meta = [
        ("Model", m.model),
        ("Prompt", m.prompt_version),
        ("Dataset", f"{m.dataset_version}, {m.total_cases} cases"),
        ("Run", f"#{len(entries)}, {when(m.timestamp)} UTC"),
    ]
    if last.label:
        meta.append(("Note", last.label))
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in meta)
    return (
        f'<div class="sign {"ok" if ok else "bad"}" role="status">'
        f'<div class="sign-top"><span>QUALITY GATE</span><span class="run">Run {len(entries)}</span></div>'
        f'<div class="sign-status"><span class="light" aria-hidden="true"></span>'
        f'<span class="status-word"><span aria-hidden="true">{icon} </span>{word}</span></div>'
        f'<p class="sign-why">{esc(why)}</p><dl class="sign-meta">{dl}</dl></div>'
    )


NAV = [("trends", "Trends"), ("categories", "Categories"), ("runs", "Runs"), ("details", "Details")]


def _section(key: str, title: str, *parts: str) -> str:
    return f'<section class="block" id="{key}"><h2>{esc(title)}</h2>{"".join(parts)}</section>'


def render_html(entries: list[HistoryEntry], latest: RunResult | None = None) -> str:
    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Travel AI Eval Trends</title><style>{CSS}</style></head><body>"
    )
    tail = f'<div id="tip" role="tooltip"></div><script>{JS}</script></body></html>'
    bar = (
        '<header class="top"><div class="bar"><span class="brand">Travel AI Evaluation</span><nav>'
        + "".join(f'<a href="#{k}">{t}</a>' for k, t in NAV)
        + "</nav></div></header>"
    )
    if not entries:
        body = (
            "<main><h1>Travel AI evaluation</h1><p class='cap'>No runs recorded yet. Run "
            "<code>uv run python -m travel_ai_eval.evaluation.runner</code> to create the first entry.</p></main>"
        )
        return head + bar + body + tail

    changes = changes_vs_previous(entries)
    last = entries[-1]
    m = last.metadata
    failures = None
    if latest is not None and latest.metadata.timestamp == m.timestamp:
        failures = fold(
            f"Failures in the latest run ({when(m.timestamp)})",
            intro("failures") + render_failures(latest),
            open_=any(not k.passed for c in latest.cases for k in c.deterministic.checks),
        )
    details = [
        fold("Quality gate: why PASS or FAIL", intro("gate") + render_gate_table(last), open_=True),
        fold("Case stability", intro("stability") + render_matrix(entries, changes)),
        fold("Results by configuration", intro("configs") + render_configs(entries)),
        failures or "",
        fold("Not measured yet", intro("unmeasured") + render_not_measured(entries)),
        fold("What the metrics mean", intro("glossary") + render_glossary()),
    ]
    body = [
        '<main><div class="hero">',
        render_sign(entries),
        render_keys(entries),
        "</div>",
        render_summary(entries),
        render_how_to_read(),
        _section(
            "trends",
            "Trends",
            intro("trends"),
            render_single_run_note() if len(entries) == 1 else "",
            '<p class="legend">● earlier runs, <span class="now">●</span> the latest run, <span class="diamond">◆</span> a run below the required level (shaded)</p>',
            f'<div class="panels">{"".join(render_panel(p, entries, changes) for p in PANELS)}</div>',
        ),
        _section("categories", "Results by category", intro("categories"), render_categories(entries)),
        _section("runs", "What changed, run by run", intro("runs"), render_runs_table(entries, changes)),
        _section("details", "Details", "".join(details)),
        f"<footer>Built from reports/history.jsonl: {len(entries)} recorded run(s).</footer></main>",
    ]
    return head + bar + "".join(body) + tail


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
