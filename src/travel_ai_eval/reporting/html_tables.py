"""Table renderers for the HTML report (run history, configurations, case matrix, failures)."""

from travel_ai_eval.models.results import RunResult
from travel_ai_eval.reporting.history import HistoryEntry
from travel_ai_eval.reporting.html_common import (
    PANELS,
    esc,
    fmt,
    metric_value,
    run_lines,
    tip_attr,
    when,
)

MATRIX_RUNS = 12





_FIELD_NAMES = {
    "model": "model",
    "prompt_version": "prompt",
    "judge_prompt_version": "judge prompt",
    "groundedness_prompt_version": "groundedness prompt",
    "dataset_version": "dataset",
}


def _line(changed: set[str], field: str, text: str) -> str:
    cls = ' class="chg"' if field in changed else ""
    return f"<span{cls}>{esc(text)}</span>"


def _pretty_change(change: str) -> str:
    field, _, rest = change.partition(": ")
    return f"{_FIELD_NAMES.get(field, field)} {rest}"


def render_runs_table(entries: list[HistoryEntry], changes: list[list[str]]) -> str:
    head = ["Run", "When (UTC)", "Gate", "What changed", "Configuration", "Constraints", "Schema",
            "Relevance", "Grounded.", "Helpful.", "Instr."]
    rows = []
    for i in reversed(range(len(entries))):
        e, m = entries[i], entries[i].metadata
        changed = {c.split(":")[0] for c in changes[i]}

        verdict = '<span class="chip pass">✓ PASS</span>' if e.gate.passed else '<span class="chip fail">✕ FAIL</span>'
        commit = (e.git_commit or "no commit recorded") + (" (uncommitted changes)" if e.git_dirty else "")
        what = esc(e.label or "")
        chips = "".join(f'<span class="chg-chip">{esc(_pretty_change(c))}</span>' for c in changes[i])
        cfg_title = (
            f"judge prompt {m.judge_prompt_version}, groundedness prompt {m.groundedness_prompt_version}"
        )
        rows.append(
            f"<tr{' class=\"latest\"' if i == len(entries) - 1 else ''}><td><span class='run-no'>{i + 1}</span></td>"
            f"<td>{esc(when(m.timestamp))}<div class='note'>{esc(commit)}</div></td>"
            f"<td>{verdict}</td>"
            f"<td class='wrap'>{what}<div>{chips}</div></td>"
            f"<td><div class='cfg' title='{esc(cfg_title)}'>"
            f"{_line(changed, 'model', m.model)}{_line(changed, 'prompt_version', 'prompt ' + m.prompt_version)}"
            f"{_line(changed, 'dataset_version', 'dataset ' + m.dataset_version + ', ' + str(m.total_cases) + ' cases')}</div></td>"
            + "".join(
                f"<td class='num'>{fmt(metric_value(e, p.attr), p.is_rate)}</td>" for p in PANELS[:5]
            )
            + f"<td class='num'>{fmt(e.metrics.avg_instruction_following, False)}</td></tr>"
        )
    head_html = "".join(f"<th>{h}</th>" for h in head)
    return (
        '<div class="tablewrap"><table><thead><tr>' + head_html + "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
        '<p class="note">Highlighted = changed since the previous run. Hover a row\'s configuration for the judge and groundedness prompt versions.</p>'
    )


def render_configs(entries: list[HistoryEntry]) -> str:
    groups: dict[tuple[str, ...], list[HistoryEntry]] = {}
    for e in entries:
        groups.setdefault(e.signature, []).append(e)
    cols = PANELS[:5]
    rows = []
    for sig, es in groups.items():
        cells = []
        for p in cols:
            vs = [v for e in es if (v := metric_value(e, p.attr)) is not None]
            if not vs:
                cells.append("<td class='num'>n/a</td>")
            elif len(vs) == 1:
                cells.append(f"<td class='num'>{fmt(vs[0], p.is_rate)}</td>")
            else:
                mean = sum(vs) / len(vs)
                cells.append(
                    f"<td class='num'>{fmt(mean, p.is_rate)} <span class='note'>"
                    f"({fmt(min(vs), p.is_rate)}–{fmt(max(vs), p.is_rate)})</span></td>"
                )
        passed = sum(e.gate.passed for e in es)
        rows.append(
            f"<tr><td class='wrap'>{esc(sig[0])}<div class='note'>prompt {esc(sig[1])}, judge {esc(sig[2])}, groundedness {esc(sig[3])}, dataset {esc(sig[4])}</div></td>"
            f"<td class='num'>{len(es)}</td><td class='num'>{passed}/{len(es)}</td>{''.join(cells)}</tr>"
        )
    head = "".join(f"<th>{h}</th>" for h in ["Configuration", "Runs", "Gate passed"] + [p.label for p in cols])
    return (
        '<div class="tablewrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
        '<p class="note">Mean with (min–max) across runs of the same configuration. A wide range '
        "means single runs of that configuration are not trustworthy on their own.</p>"
    )


def render_matrix(entries: list[HistoryEntry], changes: list[list[str]]) -> str:
    shown = entries[-MATRIX_RUNS:]
    offset = len(entries) - len(shown)
    fails: dict[str, int] = {}
    for e in shown:
        for c in e.cases:
            if not c.passed:
                fails[c.case_id] = fails.get(c.case_id, 0) + 1
    if not fails:
        return f'<p class="note">No case failed a deterministic check in the last {len(shown)} run(s).</p>'
    head = "".join(
        f'<th title="{esc(when(e.metadata.timestamp))}">#{offset + i + 1}</th>' for i, e in enumerate(shown)
    )
    rows = []
    for case_id, count in sorted(fails.items(), key=lambda kv: (-kv[1], kv[0])):
        cells = []
        for i, e in enumerate(shown):
            c = next((c for c in e.cases if c.case_id == case_id), None)
            if c is None:
                cells.append('<td class="cell none"><span>·</span></td>')
                continue
            verdict = "PASS" if c.passed else "FAIL"
            lines = [f"failed: {', '.join(c.failed_checks)}"] if c.failed_checks else []
            tip = tip_attr(f"{case_id} · run #{offset + i + 1}", verdict, lines + run_lines(e, changes[offset + i]))
            glyph, cls = ("✓", "ok") if c.passed else ("✕", "bad")
            cells.append(f'<td class="cell {cls}" tabindex="0" aria-label="{verdict}" data-tip="{tip}"><span>{glyph}</span></td>')
        rows.append(f"<tr><td>{esc(case_id)}</td><td class='num'>{count}</td>{''.join(cells)}</tr>")
    total = len({c.case_id for e in shown for c in e.cases})
    return (
        '<div class="tablewrap"><table><thead><tr><th>Case</th><th>Failures</th>' + head + "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
        f'<p class="note">Only cases that failed at least once in these runs are listed '
        f"({len(fails)} of {total}). ✓ passed, ✕ failed, a dot means the case was not in that run's dataset. Cases that flip between runs are flaky.</p>"
    )


def render_failures(latest: RunResult) -> str:
    rows = []
    for c in latest.cases:
        for k in c.deterministic.checks:
            if not k.passed:
                rows.append(f"<tr><td>{esc(c.case_id)}</td><td>{esc(k.name)}</td><td class='wrap'>{esc(k.reason)}</td></tr>")
        for kind, err in (("judge", c.judge_error), ("groundedness", c.groundedness_error)):
            if err:
                rows.append(f"<tr><td>{esc(c.case_id)}</td><td>{kind}</td><td class='wrap'>{esc(err)}</td></tr>")
    if not rows:
        return '<p class="note">No failed checks in the latest full run.</p>'
    return (
        '<div class="tablewrap"><table><thead><tr><th>Case</th><th>Check</th><th>Reason</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>"
    )
