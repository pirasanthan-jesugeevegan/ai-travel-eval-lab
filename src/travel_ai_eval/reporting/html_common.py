"""Shared pieces of the HTML report: metric panels, formatting and tooltip helpers."""

import html
import json
from dataclasses import dataclass
from datetime import datetime

from travel_ai_eval.reporting.history import HistoryEntry


@dataclass(frozen=True)
class Panel:
    attr: str  # RunMetrics field
    label: str
    is_rate: bool
    gate: str | None  # matching GateCheck name, if the metric is gated


PANELS = [
    Panel("constraint_satisfaction", "Constraint satisfaction", True, "constraint_satisfaction"),
    Panel("schema_validity", "Schema validity", True, "schema_validity"),
    Panel("avg_relevance", "Relevance", False, "relevance"),
    Panel("avg_groundedness", "Groundedness", False, "groundedness"),
    Panel("avg_helpfulness", "Helpfulness", False, "helpfulness"),
    Panel("avg_instruction_following", "Instruction following", False, None),
]


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def fmt(value: float | None, is_rate: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%" if is_rate else f"{value:.2f}"


def when(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%b %d %H:%M")
    except ValueError:
        return ts


def tip_attr(title: str, value: str, lines: list[str]) -> str:
    return esc(json.dumps({"title": title, "value": value, "lines": lines}))


def run_lines(e: HistoryEntry, changed: list[str]) -> list[str]:
    m = e.metadata
    lines = [
        m.model,
        f"prompt {m.prompt_version} · judge {m.judge_prompt_version} · dataset {m.dataset_version}",
    ]
    if e.label:
        lines.append(e.label)
    if e.git_commit:
        lines.append(f"commit {e.git_commit}{' (+uncommitted changes)' if e.git_dirty else ''}")
    lines += [f"Changed: {c}" for c in changed]
    return lines


def metric_value(e: HistoryEntry, attr: str) -> float | None:
    return getattr(e.metrics, attr)
