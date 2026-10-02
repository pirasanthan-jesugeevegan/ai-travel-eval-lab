"""The metrics shown in reports: one definition used by the terminal and HTML reports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    attr: str  # field name on RunMetrics
    label: str
    is_rate: bool  # True: a 0-1 share shown as %, False: a 1-5 score
    gate: str | None  # matching quality-gate check name, None if not gated
    kind: str  # "Rule-based" or "LLM-judged"
    meaning: str  # plain-English explanation shown in the HTML report


METRICS = [
    Metric("schema_validity", "Schema validity", True, "schema_validity", "Rule-based",
           "Share of replies that were valid JSON in the required shape. A malformed reply is "
           "unusable, so the gate requires 100%."),
    Metric("constraint_satisfaction", "Constraint satisfaction", True, "constraint_satisfaction",
           "Rule-based",
           "Share of cases where every rule-based check passed: right city, within budget, "
           "hotel exists, family / cancellation / beach / rating needs met, nothing leaked."),
    Metric("inventory_accuracy", "Inventory accuracy", True, None, "Rule-based",
           "Share of cases where every recommended hotel ID exists in the inventory "
           "(no invented hotels)."),
    Metric("avg_relevance", "Relevance", False, "relevance", "LLM-judged",
           "Score 1-5 from an LLM judge: does the reply answer what the user actually asked?"),
    Metric("avg_groundedness", "Groundedness", False, "groundedness", "LLM-judged",
           "Score 1-5 from a separate LLM check: is every claim backed by the inventory, "
           "with no invented facts?"),
    Metric("avg_helpfulness", "Helpfulness", False, "helpfulness", "LLM-judged",
           "Score 1-5 from an LLM judge: could the user act on the reply, e.g. does it offer a "
           "useful next step?"),
    Metric("avg_instruction_following", "Instruction following", False, None, "LLM-judged",
           "Score 1-5 from an LLM judge: did the assistant follow its rules (stay in role, keep "
           "its instructions private, admit what it does not know)? Reported, not gated."),
]
METRIC_BY_ATTR = {m.attr: m for m in METRICS}


def fmt(value: float | None, is_rate: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%" if is_rate else f"{value:.2f}"
