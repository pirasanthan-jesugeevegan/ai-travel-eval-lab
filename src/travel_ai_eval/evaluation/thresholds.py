"""Quality gate: compare run metrics with configurable minimum thresholds.

Rates are fractions (0.95 = 95%); LLM scores are on the 1-5 scale. Every threshold must
be met - a high LLM score can never compensate for a deterministic failure.
"""

import os

from pydantic import BaseModel

from travel_ai_eval.models.results import GateCheck, GateResult, RunMetrics

ENV_PREFIX = "EVAL_MIN_"


class Thresholds(BaseModel):
    schema_validity: float = 1.0
    constraint_satisfaction: float = 0.95
    relevance: float = 4.3
    groundedness: float = 4.5
    helpfulness: float = 4.3
    # Share of cases the LLM judges must have scored; stops failed judge calls
    # from silently shrinking the sample the averages are computed on.
    judge_coverage: float = 0.9

    @classmethod
    def from_env(cls) -> "Thresholds":
        """Override defaults with e.g. EVAL_MIN_RELEVANCE=4.0."""
        overrides: dict[str, float] = {}
        for name in cls.model_fields:
            raw = os.environ.get(ENV_PREFIX + name.upper())
            if raw:
                try:
                    overrides[name] = float(raw)
                except ValueError:
                    raise ValueError(f"{ENV_PREFIX}{name.upper()} must be a number, got {raw!r}") from None
        return cls(**overrides)


def evaluate_gate(metrics: RunMetrics, total_cases: int, thresholds: Thresholds) -> GateResult:
    judge_coverage = metrics.judge_scored_cases / total_cases if total_cases else 0.0
    actuals: dict[str, float | None] = {
        "schema_validity": metrics.schema_validity,
        "constraint_satisfaction": metrics.constraint_satisfaction,
        "relevance": metrics.avg_relevance,
        "groundedness": metrics.avg_groundedness,
        "helpfulness": metrics.avg_helpfulness,
        "judge_coverage": judge_coverage,
    }
    checks = []
    for name, actual in actuals.items():
        threshold = getattr(thresholds, name)
        # A metric that could not be computed (no scored cases) fails the gate.
        checks.append(
            GateCheck(
                name=name,
                threshold=threshold,
                actual=actual,
                passed=actual is not None and actual >= threshold,
            )
        )
    return GateResult(passed=all(c.passed for c in checks), checks=checks)
