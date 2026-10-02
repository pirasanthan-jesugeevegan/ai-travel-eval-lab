"""Explanatory sections of the HTML report: how to read it, summary, gate table, categories,
glossary and honest placeholders for things that are not measured yet."""

from travel_ai_eval.reporting.history import HistoryEntry
from travel_ai_eval.reporting.html_common import esc, fmt
from travel_ai_eval.reporting.metrics import METRICS

_TOLERANCE = 0.005

CATEGORY_HELP = {
    "normal": "Everyday requests: a city break, a beach holiday, a family trip.",
    "budget": "Requests with a price limit. The assistant must stay at or under it.",
    "attribute": "Requests for a specific feature: free cancellation, beach access, family friendly, rating.",
    "multi_constraint": "Several requirements at once. The hardest everyday case.",
    "ambiguous": "Vague requests (\"somewhere warm\"). Help without inventing requirements.",
    "conflicting": "Requirements no hotel can meet. The assistant must say so, not make something up.",
    "impossible": "Requests outside the inventory (e.g. a hotel on Mars).",
    "hallucination_trap": "Questions about hotels or facts that are not in the inventory.",
    "prompt_injection": "Attempts to make the assistant leak its instructions or ignore its rules.",
}

SECTION_INTRO = {
    "gate": "The quality gate is the release decision. It passes only if every row below passes; "
    "a strong score on one row can never make up for a failure on another.",
    "trends": "One chart per metric, each on its own scale, with the required threshold drawn on it. "
    "Vertical hairlines mark a change of model, prompt or dataset version between two runs, "
    "so you can see what a change did. Hover or focus a run for details.",
    "categories": "Where do failures come from? Each row is a kind of request. The numbers are "
    "cases that passed every rule-based check. Compare the latest run with the one before it.",
    "runs": "Every recorded run, newest first. Bold cells changed since the previous run, so this "
    "is the place to match a drop in a metric to the change that caused it.",
    "configs": "Runs grouped by identical configuration (same model, prompts and dataset). The "
    "range shows how much the results move between runs that should be identical: LLMs are not "
    "deterministic, so a single run is only a sample.",
    "stability": "Cases that failed a rule-based check in at least one recent run. A case that "
    "flips between pass and fail across runs is flaky: the model's behaviour on it is unreliable.",
    "failures": "Exactly which checks failed in the most recent full run, and why.",
    "unmeasured": "Things a production monitoring setup would track that this project does not "
    "measure yet. Listed so nobody mistakes their absence for a good result.",
    "glossary": "What each metric means, and whether a rule or an LLM produced it.",
}


def intro(key: str) -> str:
    return f'<p class="sub">{esc(SECTION_INTRO[key])}</p>'


def render_how_to_read() -> str:
    return (
        '<details class="box" open><summary><b>How to read this page</b></summary><ol>'
        "<li>This project tests a travel assistant (an LLM) against a fixed set of questions with "
        "known right answers. Each <b>run</b> asks every question once and scores the replies.</li>"
        "<li><b>Rule-based</b> metrics are exact checks (is the price within budget? does the "
        "hotel exist?). <b>LLM-judged</b> metrics are 1-5 scores from a second model for things "
        "rules cannot measure (helpfulness, honesty). Rule-based failures can never be "
        "outvoted by a good LLM score.</li>"
        "<li>The <b>quality gate</b> turns the metrics into PASS or FAIL against fixed thresholds. "
        "The <b>trends</b> show whether a change to the model, prompt or data made things "
        "better or worse.</li></ol></details>"
    )


def _moved(prev: HistoryEntry, cur: HistoryEntry) -> list[str]:
    out = []
    for m in METRICS:
        a, b = getattr(prev.metrics, m.attr), getattr(cur.metrics, m.attr)
        if a is None or b is None or abs(b - a) < _TOLERANCE:
            continue
        verb = "rose" if b > a else "fell"
        out.append(f"{m.label.lower()} {verb} from {fmt(a, m.is_rate)} to {fmt(b, m.is_rate)}")
    return out


def render_summary(entries: list[HistoryEntry]) -> str:
    last = entries[-1]
    m = last.metrics
    checks = {c.name: c for c in last.gate.checks}
    cons = checks.get("constraint_satisfaction")
    text = (
        f"Run #{len(entries)} tested {last.metadata.total_cases} questions. "
        f"{fmt(m.constraint_satisfaction, True)} passed every rule-based check"
        + (f" (the gate requires {fmt(cons.threshold, True)})" if cons else "")
        + ". "
        f"Average LLM scores out of 5: relevance {fmt(m.avg_relevance, False)}, groundedness "
        f"{fmt(m.avg_groundedness, False)}, helpfulness {fmt(m.avg_helpfulness, False)}."
    )
    if len(entries) > 1:
        moved = _moved(entries[-2], last)
        text += (
            " Since the previous run: " + "; ".join(moved) + "."
            if moved
            else " Nothing moved noticeably since the previous run."
        )
    else:
        text += " This is the first recorded run, so there is nothing to compare with yet."
    return f'<p class="summary">{esc(text)}</p>'


def render_gate_table(last: HistoryEntry) -> str:
    by_gate = {m.gate: m for m in METRICS if m.gate}
    rows = []
    for c in last.gate.checks:
        metric = by_gate.get(c.name)
        label = metric.label if metric else "Judge coverage"
        is_rate = metric.is_rate if metric else True
        meaning = (
            metric.meaning
            if metric
            else "Share of cases the LLM judge managed to score. Stops failed judge calls from "
            "quietly shrinking the sample behind the averages."
        )
        status = '<span class="pass">✓ PASS</span>' if c.passed else '<span class="fail">✕ FAIL</span>'
        rows.append(
            f"<tr><td>{esc(label)}</td><td class='num'>≥ {fmt(c.threshold, is_rate)}</td>"
            f"<td class='num'>{fmt(c.actual, is_rate)}</td><td>{status}</td>"
            f"<td class='wrap'>{esc(meaning)}</td></tr>"
        )
    return (
        '<div class="tablewrap"><table><thead><tr><th>Check</th><th>Required</th><th>Actual</th>'
        "<th>Result</th><th>What it means</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _category_counts(e: HistoryEntry) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = {}
    for c in e.cases:
        passed_total = counts.setdefault(c.category, [0, 0])
        passed_total[0] += c.passed
        passed_total[1] += 1
    return {k: (v[0], v[1]) for k, v in counts.items()}


def render_categories(entries: list[HistoryEntry]) -> str:
    cur = _category_counts(entries[-1])
    prev = _category_counts(entries[-2]) if len(entries) > 1 else {}
    rows = []
    for cat in sorted(cur, key=lambda c: (cur[c][0] / cur[c][1], c)):
        ok, total = cur[cat]
        change = ""
        if cat in prev:
            pok, ptotal = prev[cat]
            diff = ok / total - pok / ptotal
            change = "▲ better" if diff > 0.0001 else "▼ worse" if diff < -0.0001 else "— same"
        cls = "pass" if ok == total else "fail"
        mark = "✓" if ok == total else "✕"
        rows.append(
            f"<tr><td>{esc(cat.replace('_', ' '))}</td><td class='wrap'>{esc(CATEGORY_HELP.get(cat, ''))}</td>"
            f"<td class='num'><span class='{cls}'>{mark} {ok}/{total}</span></td>"
            f"<td>{esc(change) or '<span class=note>n/a</span>'}</td></tr>"
        )
    return (
        '<div class="tablewrap"><table><thead><tr><th>Category</th><th>What it tests</th>'
        "<th>Passed (latest run)</th><th>vs previous run</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
    )


def render_not_measured(entries: list[HistoryEntry]) -> str:
    sizes: dict[tuple[str, ...], int] = {}
    for e in entries:
        sizes[e.signature] = sizes.get(e.signature, 0) + 1
    best = max(sizes.values())
    variance = (
        ("Partly measured", f"{best} runs of the same configuration so far. See Results by configuration.")
        if best >= 3
        else ("Not enough data", f"Needs 3 or more runs of one configuration (best so far: {best}).")
    )
    items = [
        ("Run-to-run variance", *variance,
         "Shows how much a score moves with no change at all, i.e. how big a drop must be to count."),
        ("Latency per reply", "Not measured yet", "",
         "Slow replies hurt the user. Production tracking watches the median and the slowest 5%."),
        ("Token usage and cost per run", "Not measured yet", "",
         "Catches a prompt change that quietly makes every request more expensive."),
        ("LLM judge vs human agreement", "Not measured yet", "",
         "Shows whether the judge's scores can be trusted. Needs people to score a sample of replies."),
    ]
    rows = "".join(
        f"<tr><td>{esc(name)}</td><td><span class='todo'>{esc(status)}</span> {esc(detail)}</td>"
        f"<td class='wrap'>{esc(why)}</td></tr>"
        for name, status, detail, why in items
    )
    return (
        '<div class="tablewrap"><table><thead><tr><th>Item</th><th>Status</th><th>Why it matters</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def render_glossary() -> str:
    rows = "".join(
        f"<tr><td>{esc(m.label)}</td><td>{esc(m.kind)}</td><td class='wrap'>{esc(m.meaning)}</td></tr>"
        for m in METRICS
    )
    return (
        '<div class="tablewrap"><table><thead><tr><th>Metric</th><th>Produced by</th>'
        f"<th>Meaning</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def render_single_run_note() -> str:
    return (
        '<p class="box note-box">Only one run is recorded, so there is no trend to draw yet. '
        "Run the evaluation again after a change to the prompt, model or dataset and the charts "
        "will fill in.</p>"
    )

