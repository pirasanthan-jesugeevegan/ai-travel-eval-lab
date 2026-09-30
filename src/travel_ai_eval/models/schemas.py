"""Pydantic models shared by the agent, the dataset and the evaluators."""

from typing import Literal

from pydantic import BaseModel, Field, computed_field


class InventoryItem(BaseModel):
    """A single synthetic hotel/product. The source of truth for evaluation."""

    id: str
    name: str
    destination: str
    country: str
    price_gbp: float = Field(gt=0)
    family_friendly: bool
    free_cancellation: bool
    beach_access: bool
    rating: float = Field(ge=0, le=5)


class Recommendation(BaseModel):
    hotel_id: str
    reason: str


class TravelResponse(BaseModel):
    """Structured output the travel agent must return."""

    answer: str
    recommendations: list[Recommendation]


class Constraints(BaseModel):
    """Expected constraints for a golden case. None means 'not specified'."""

    destination: str | None = None
    country: str | None = None
    max_budget_gbp: float | None = Field(default=None, gt=0)
    family_friendly: bool | None = None
    free_cancellation: bool | None = None
    beach_access: bool | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)


Category = Literal[
    "normal",
    "budget",
    "attribute",
    "multi_constraint",
    "ambiguous",
    "conflicting",
    "impossible",
    "hallucination_trap",
    "prompt_injection",
]


class GoldenCase(BaseModel):
    id: str
    category: Category
    query: str
    language: str = "en"
    constraints: Constraints = Field(default_factory=Constraints)
    # True when the correct behaviour is to recommend nothing (impossible request,
    # unknown hotel, injection attempt). Used by deterministic checks only, never shown to the judge.
    expect_no_recommendations: bool = False


class GoldenDataset(BaseModel):
    version: str
    cases: list[GoldenCase]


class CheckResult(BaseModel):
    name: str
    passed: bool
    reason: str


class EvalResult(BaseModel):
    """Outcome of all deterministic checks for one case. Passes only if every check passes."""

    checks: list[CheckResult]

    @computed_field
    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)
