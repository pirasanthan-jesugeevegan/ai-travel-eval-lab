"""Shared pieces of the HTML report: chart order, escaping, tooltip helpers."""

import html
import json
from datetime import datetime

from travel_ai_eval.reporting.history import HistoryEntry
from travel_ai_eval.reporting.metrics import METRIC_BY_ATTR, fmt

# Order of the trend charts (the first five are the gated metrics).
PANELS = [
    METRIC_BY_ATTR[a]
    for a in (
        "constraint_satisfaction", "schema_validity", "avg_relevance",
        "avg_groundedness", "avg_helpfulness", "avg_instruction_following",
    )
]


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


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
        f"prompt {m.prompt_version} · judge {m.judge_prompt_version} · "
        f"groundedness {m.groundedness_prompt_version} · dataset {m.dataset_version}",
    ]
    if e.label:
        lines.append(e.label)
    if e.git_commit:
        lines.append(f"commit {e.git_commit}{' (+uncommitted changes)' if e.git_dirty else ''}")
    lines += [f"Changed: {c}" for c in changed]
    return lines


def metric_value(e: HistoryEntry, attr: str) -> float | None:
    return getattr(e.metrics, attr)


__all__ = ["PANELS", "esc", "fmt", "metric_value", "run_lines", "tip_attr", "when"]
