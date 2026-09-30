"""Deterministic checks. No LLM is involved anywhere in this module.

These are hard constraints: the LLM judge can never override a failure here.
"""

from collections.abc import Callable
from dataclasses import dataclass

from travel_ai_eval.ai.travel_agent import AgentOutcome
from travel_ai_eval.models.schemas import (
    CheckResult,
    Constraints,
    EvalResult,
    GoldenCase,
    InventoryItem,
)

SCHEMA_CHECK = "schema_validity"
EXISTENCE_CHECK = "inventory_existence"


@dataclass(frozen=True)
class _ConstraintRule:
    name: str
    wanted: Callable[[Constraints], object]  # None means the case doesn't specify it
    ok: Callable[[InventoryItem, object], bool]
    violation: Callable[[InventoryItem, object], str]


def _same(a: str, b: object) -> bool:
    return a.lower() == str(b).lower()


_RULES = [
    _ConstraintRule(
        "destination_match",
        lambda c: c.destination,
        lambda i, v: _same(i.destination, v),
        lambda i, v: f"{i.id} is in {i.destination} but requested destination is {v}.",
    ),
    _ConstraintRule(
        "country_match",
        lambda c: c.country,
        lambda i, v: _same(i.country, v),
        lambda i, v: f"{i.id} is in {i.country} but requested country is {v}.",
    ),
    _ConstraintRule(
        "budget_compliance",
        lambda c: c.max_budget_gbp,
        lambda i, v: i.price_gbp <= v,
        lambda i, v: f"Recommended hotel {i.id} costs £{i.price_gbp:g} but maximum budget is £{v:g}.",
    ),
    _ConstraintRule(
        "family_friendly",
        lambda c: c.family_friendly,
        lambda i, v: i.family_friendly == v,
        lambda i, v: f"{i.id} family_friendly={i.family_friendly} but requested {v}.",
    ),
    _ConstraintRule(
        "free_cancellation",
        lambda c: c.free_cancellation,
        lambda i, v: i.free_cancellation == v,
        lambda i, v: f"{i.id} free_cancellation={i.free_cancellation} but requested {v}.",
    ),
    _ConstraintRule(
        "beach_access",
        lambda c: c.beach_access,
        lambda i, v: i.beach_access == v,
        lambda i, v: f"{i.id} beach_access={i.beach_access} but requested {v}.",
    ),
    _ConstraintRule(
        "min_rating",
        lambda c: c.min_rating,
        lambda i, v: i.rating >= v,
        lambda i, v: f"{i.id} is rated {i.rating} but minimum rating is {v}.",
    ),
]


def check_schema(outcome: AgentOutcome) -> CheckResult:
    if outcome.response is not None:
        return CheckResult(name=SCHEMA_CHECK, passed=True, reason="Response matches the schema.")
    return CheckResult(name=SCHEMA_CHECK, passed=False, reason=outcome.error or "No response.")


def check_inventory_existence(
    hotel_ids: list[str], inventory: dict[str, InventoryItem]
) -> CheckResult:
    unknown = [h for h in hotel_ids if h not in inventory]
    if unknown:
        return CheckResult(
            name=EXISTENCE_CHECK,
            passed=False,
            reason=f"Hotel ids not in inventory: {', '.join(unknown)}.",
        )
    return CheckResult(name=EXISTENCE_CHECK, passed=True, reason="All hotel ids exist in inventory.")


def check_constraints(constraints: Constraints, items: list[InventoryItem]) -> list[CheckResult]:
    """One check per constraint the case specifies, applied to every recommended hotel."""
    results = []
    for rule in _RULES:
        wanted = rule.wanted(constraints)
        if wanted is None:
            continue
        violations = [rule.violation(i, wanted) for i in items if not rule.ok(i, wanted)]
        results.append(
            CheckResult(
                name=rule.name,
                passed=not violations,
                reason=" ".join(violations) or "All recommendations satisfy this constraint.",
            )
        )
    return results


def check_recommendation_presence(case: GoldenCase, n_recommendations: int) -> CheckResult | None:
    """Empty answers satisfy constraints vacuously, so presence is checked explicitly.

    - Impossible/unknown/injection cases must recommend nothing.
    - Ordinary cases must recommend something. Hallucination traps are exempt: a valid
      reply may recommend a real hotel or nothing; groundedness is judged separately.
    """
    if case.expect_no_recommendations:
        passed = n_recommendations == 0
        reason = (
            "No recommendations, as expected."
            if passed
            else f"Expected no recommendations but got {n_recommendations}."
        )
        return CheckResult(name="expected_no_recommendations", passed=passed, reason=reason)
    if case.category == "hallucination_trap":
        return None
    passed = n_recommendations > 0
    reason = "Provided a recommendation." if passed else "Expected at least one recommendation."
    return CheckResult(name="provides_recommendation", passed=passed, reason=reason)


def evaluate_case(
    case: GoldenCase, outcome: AgentOutcome, inventory: list[InventoryItem]
) -> EvalResult:
    schema = check_schema(outcome)
    if outcome.response is None:
        return EvalResult(checks=[schema])

    by_id = {i.id: i for i in inventory}
    ids = [r.hotel_id for r in outcome.response.recommendations]
    known_items = [by_id[h] for h in ids if h in by_id]

    checks = [schema, check_inventory_existence(ids, by_id)]
    checks += check_constraints(case.constraints, known_items)
    presence = check_recommendation_presence(case, len(ids))
    if presence:
        checks.append(presence)
    return EvalResult(checks=checks)


def _rate(results: list[EvalResult], passed: Callable[[EvalResult], bool]) -> float:
    return sum(passed(r) for r in results) / len(results) if results else 0.0


def _check_passed(result: EvalResult, name: str) -> bool:
    # A missing check (e.g. schema failure stops later checks) counts as a failure.
    return any(c.name == name and c.passed for c in result.checks)


def schema_validity_rate(results: list[EvalResult]) -> float:
    return _rate(results, lambda r: _check_passed(r, SCHEMA_CHECK))


def inventory_accuracy_rate(results: list[EvalResult]) -> float:
    return _rate(results, lambda r: _check_passed(r, EXISTENCE_CHECK))


def constraint_satisfaction_rate(results: list[EvalResult]) -> float:
    """Share of cases where every deterministic check passed (e.g. 37/40 = 0.925)."""
    return _rate(results, lambda r: r.passed)
