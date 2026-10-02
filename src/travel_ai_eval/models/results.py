"""Result models for one evaluation run."""

from pydantic import BaseModel

from travel_ai_eval.models.schemas import (
    EvalResult,
    GroundednessVerdict,
    JudgeScores,
    TravelResponse,
)


class RunMetadata(BaseModel):
    """Everything needed to interpret (and compare) a run: results change with any of these."""

    timestamp: str
    model: str
    dataset_version: str
    prompt_version: str
    judge_prompt_version: str
    groundedness_prompt_version: str = "1.0.0"  # default: runs recorded before this field existed
    total_cases: int


class CaseResult(BaseModel):
    case_id: str
    category: str
    query: str
    response: TravelResponse | None
    raw_output: str
    agent_error: str | None
    deterministic: EvalResult
    judge: JudgeScores | None = None
    judge_error: str | None = None
    groundedness: GroundednessVerdict | None = None
    groundedness_error: str | None = None


class RunMetrics(BaseModel):
    """Rates are 0-1 fractions over all cases; LLM averages (1-5) are over scored cases only."""

    schema_validity: float
    inventory_accuracy: float
    constraint_satisfaction: float
    avg_relevance: float | None
    avg_groundedness: float | None  # from the dedicated groundedness check
    avg_helpfulness: float | None
    avg_instruction_following: float | None
    avg_judge_constraint_satisfaction: float | None
    judge_scored_cases: int
    groundedness_scored_cases: int


class GateCheck(BaseModel):
    name: str
    threshold: float
    actual: float | None
    passed: bool


class GateResult(BaseModel):
    """PASS only if every threshold is met. No metric can compensate for another."""

    passed: bool
    checks: list[GateCheck]

    @property
    def verdict(self) -> str:
        return "PASS" if self.passed else "FAIL"


class RunResult(BaseModel):
    metadata: RunMetadata
    metrics: RunMetrics
    gate: GateResult
    cases: list[CaseResult]
