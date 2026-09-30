"""Terminal report, JSON report and baseline-vs-current comparison."""

from dataclasses import dataclass
from pathlib import Path

from travel_ai_eval.config import REPORTS_DIR
from travel_ai_eval.models.results import GateCheck, RunMetrics, RunResult
from travel_ai_eval.reporting.history import append_history, is_api_outage, summarise
from travel_ai_eval.reporting.html_report import write_html_report

LATEST_PATH = REPORTS_DIR / "latest.json"
BASELINE_PATH = REPORTS_DIR / "baseline.json"

_HEAVY = "=" * 40
_LIGHT = "-" * 40
_TOLERANCE = 0.005  # differences smaller than this are shown as unchanged

# (metric attribute, label, is a 0-1 rate)
_METRICS: list[tuple[str, str, bool]] = [
    ("schema_validity", "Schema validity", True),
    ("constraint_satisfaction", "Constraint satisfaction", True),
    ("inventory_accuracy", "Inventory accuracy", True),
    ("avg_relevance", "Relevance", False),
    ("avg_groundedness", "Groundedness", False),
    ("avg_helpfulness", "Helpfulness", False),
    ("avg_instruction_following", "Instruction following", False),
]
_GATE_LABELS = {
    "schema_validity": ("Schema validity", True),
    "constraint_satisfaction": ("Constraints", True),
    "relevance": ("Relevance", False),
    "groundedness": ("Groundedness", False),
    "helpfulness": ("Helpfulness", False),
    "judge_coverage": ("Judge coverage", True),
}


@dataclass(frozen=True)
class MetricDelta:
    label: str
    baseline: float | None
    current: float | None
    is_rate: bool

    @property
    def direction(self) -> str:
        if self.baseline is None or self.current is None:
            return ""
        diff = self.current - self.baseline
        if abs(diff) < _TOLERANCE:
            return ""
        return "↑" if diff > 0 else "↓"


def _fmt(value: float | None, is_rate: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%" if is_rate else f"{value:.2f}"


def compare_runs(baseline: RunResult, current: RunResult) -> list[MetricDelta]:
    return [
        MetricDelta(
            label,
            getattr(baseline.metrics, attr),
            getattr(current.metrics, attr),
            is_rate,
        )
        for attr, label, is_rate in _METRICS
    ]


def _metrics_section(m: RunMetrics) -> list[str]:
    def line(label: str, value: float | None, is_rate: bool) -> str:
        shown = _fmt(value, True) if is_rate else (f"{value:.2f} / 5" if value is not None else "n/a")
        return f"{label + ':':<28}{shown:>10}"

    labels = {attr: (label, is_rate) for attr, label, is_rate in _METRICS}

    def rows(attrs: list[str]) -> list[str]:
        return [line(labels[a][0], getattr(m, a), labels[a][1]) for a in attrs]

    return (
        ["Deterministic Evaluation", _LIGHT]
        + rows(["schema_validity", "constraint_satisfaction", "inventory_accuracy"])
        + ["", "LLM Evaluation", _LIGHT]
        + rows(["avg_relevance", "avg_groundedness", "avg_helpfulness", "avg_instruction_following"])
    )


def _gate_line(check: GateCheck) -> str:
    label, is_rate = _GATE_LABELS.get(check.name, (check.name, False))
    required = f"{check.threshold * 100:.0f}%" if is_rate else f"{check.threshold:g}"
    text = f"{label} >= {required}"
    return f"{text:<32}{'PASS' if check.passed else 'FAIL'}"


def _failure_lines(run: RunResult) -> list[str]:
    lines = []
    for case in run.cases:
        for check in case.deterministic.checks:
            if not check.passed:
                lines.append(f"- {case.case_id}: [{check.name}] {check.reason}")
        for kind, err in (("judge", case.judge_error), ("groundedness", case.groundedness_error)):
            if err:
                lines.append(f"- {case.case_id}: [{kind}] {err}")
    return lines


def _comparison_lines(baseline: RunResult, current: RunResult) -> list[str]:
    lines = ["Comparison with baseline", _LIGHT]
    changed = [
        f"{name}: {getattr(baseline.metadata, name)} -> {getattr(current.metadata, name)}"
        for name in ("model", "prompt_version", "dataset_version")
        if getattr(baseline.metadata, name) != getattr(current.metadata, name)
    ]
    if changed:
        lines.append("Note - runs differ in " + "; ".join(changed))
    lines.append(f"{'':<28}{'Baseline':>10}{'Current':>10}")
    for d in compare_runs(baseline, current):
        arrow = f"  {d.direction}" if d.direction else ""
        lines.append(f"{d.label:<28}{_fmt(d.baseline, d.is_rate):>10}{_fmt(d.current, d.is_rate):>10}{arrow}")
    return lines


def format_terminal_report(run: RunResult, baseline: RunResult | None = None) -> str:
    meta = run.metadata
    out = [
        _HEAVY, "Travel AI Evaluation", _HEAVY, "",
        f"Dataset: {meta.total_cases} cases (version {meta.dataset_version})",
        f"Model: {meta.model}",
        f"Prompt version: {meta.prompt_version} (judge {meta.judge_prompt_version})",
        f"Run at: {meta.timestamp}", "",
        *_metrics_section(run.metrics), "",
        "Quality Gates", _LIGHT,
        *[_gate_line(c) for c in run.gate.checks], "",
    ]
    failures = _failure_lines(run)
    if failures:
        out += ["Failures", _LIGHT, *failures, ""]
    if baseline:
        out += [*_comparison_lines(baseline, run), ""]
    out += [_HEAVY, f"QUALITY GATE: {run.gate.verdict}", _HEAVY]
    return "\n".join(out)


def write_json_report(run: RunResult, path: Path = LATEST_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_report(path: Path) -> RunResult:
    return RunResult.model_validate_json(path.read_text(encoding="utf-8"))


def save_run_outputs(
    run: RunResult, label: str | None = None, out_dir: Path = REPORTS_DIR
) -> dict[str, Path]:
    """Write latest.json, append the run to the history and regenerate the HTML trend report.

    Runs where every API call failed are written to latest.json only.
    """
    latest = write_json_report(run, out_dir / "latest.json")
    if is_api_outage(run):
        return {"json": latest}  # not an evaluation result: keep it out of history and trends
    history = out_dir / "history.jsonl"
    append_history(summarise(run, label), history)
    html = write_html_report(history, latest, out_dir / "report.html")
    return {"json": latest, "history": history, "html": html}
