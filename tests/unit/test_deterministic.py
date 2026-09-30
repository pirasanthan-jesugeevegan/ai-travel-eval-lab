import pytest
from helpers import matches

from travel_ai_eval.ai.travel_agent import AgentOutcome
from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation.deterministic import (
    constraint_satisfaction_rate,
    evaluate_case,
    inventory_accuracy_rate,
    schema_validity_rate,
)
from travel_ai_eval.models.schemas import (
    Constraints,
    GoldenCase,
    Recommendation,
    TravelResponse,
)

INVENTORY = load_inventory()
DATASET = load_dataset()


def outcome(*hotel_ids: str) -> AgentOutcome:
    resp = TravelResponse(
        answer="x", recommendations=[Recommendation(hotel_id=h, reason="r") for h in hotel_ids]
    )
    return AgentOutcome(resp, "raw")


def case(category="normal", no_recs=False, **constraints) -> GoldenCase:
    return GoldenCase(
        id="t", category=category, query="q",
        constraints=Constraints(**constraints), expect_no_recommendations=no_recs,
    )


def check(result, name):
    return next(c for c in result.checks if c.name == name)


def test_budget_fail_has_actionable_reason_and_fails_overall():
    r = evaluate_case(case(max_budget_gbp=2000), outcome("DXB003"), INVENTORY)  # £2400
    c = check(r, "budget_compliance")
    assert not c.passed and not r.passed
    assert "DXB003" in c.reason and "2400" in c.reason and "2000" in c.reason


def test_budget_boundary_is_inclusive():
    r = evaluate_case(case(max_budget_gbp=1750), outcome("DXB001"), INVENTORY)
    assert check(r, "budget_compliance").passed


@pytest.mark.parametrize(
    "constraint,bad_id,good_id",
    [
        ({"destination": "Dubai"}, "PAR001", "DXB001"),
        ({"country": "Spain"}, "PAR001", "BCN001"),
        ({"family_friendly": True}, "DXB002", "DXB001"),
        ({"free_cancellation": True}, "DXB003", "DXB001"),
        ({"beach_access": True}, "DXB002", "DXB001"),
        ({"min_rating": 4.5}, "DXB002", "DXB001"),
    ],
)
def test_each_constraint_detects_violation_and_accepts_match(constraint, bad_id, good_id):
    bad = evaluate_case(case(**constraint), outcome(bad_id), INVENTORY)
    good = evaluate_case(case(**constraint), outcome(good_id), INVENTORY)
    assert not bad.passed and good.passed


def test_destination_match_is_case_insensitive():
    assert evaluate_case(case(destination="dubai"), outcome("DXB001"), INVENTORY).passed


def test_one_bad_recommendation_among_good_fails():
    r = evaluate_case(case(max_budget_gbp=2000), outcome("DXB001", "DXB003"), INVENTORY)
    assert not r.passed


def test_unspecified_constraints_produce_no_checks():
    r = evaluate_case(case(destination="Dubai"), outcome("DXB001"), INVENTORY)
    assert {c.name for c in r.checks} == {
        "schema_validity", "inventory_existence", "destination_match", "provides_recommendation"
    }


def test_inventory_existence_catches_invented_id():
    r = evaluate_case(case(), outcome("XXX999"), INVENTORY)
    c = check(r, "inventory_existence")
    assert not c.passed and "XXX999" in c.reason and not r.passed


def test_schema_failure_short_circuits():
    r = evaluate_case(case(), AgentOutcome(None, "junk", "invalid_output: nope"), INVENTORY)
    assert [c.name for c in r.checks] == ["schema_validity"] and not r.passed
    assert "nope" in r.checks[0].reason


def test_expected_no_recommendations():
    ok = evaluate_case(case("impossible", True), outcome(), INVENTORY)
    bad = evaluate_case(case("impossible", True), outcome("DXB001"), INVENTORY)
    assert ok.passed and not bad.passed


def test_empty_answer_fails_feasible_case_despite_vacuous_constraints():
    r = evaluate_case(case(destination="Dubai"), outcome(), INVENTORY)
    assert not check(r, "provides_recommendation").passed and not r.passed


def test_hallucination_trap_allows_empty_or_real_recommendation():
    trap = case("hallucination_trap", destination="Dubai")
    assert evaluate_case(trap, outcome(), INVENTORY).passed
    assert evaluate_case(trap, outcome("DXB001"), INVENTORY).passed


def test_result_serialises_with_passed_flag():
    d = evaluate_case(case(max_budget_gbp=100), outcome("DXB001"), INVENTORY).model_dump()
    assert d["passed"] is False and d["checks"][0].keys() == {"name", "passed", "reason"}


def test_rates():
    good = evaluate_case(case(), outcome("DXB001"), INVENTORY)
    invented = evaluate_case(case(), outcome("XXX999"), INVENTORY)
    schema_bad = evaluate_case(case(), AgentOutcome(None, "", "e"), INVENTORY)
    results = [good, invented, schema_bad, good]
    assert constraint_satisfaction_rate(results) == 0.5
    assert schema_validity_rate(results) == 0.75
    assert inventory_accuracy_rate(results) == 0.5
    assert constraint_satisfaction_rate([]) == 0.0


def oracle_outcome(c: GoldenCase) -> AgentOutcome:
    if c.expect_no_recommendations or c.category == "hallucination_trap":
        return outcome()
    return outcome(*[i.id for i in INVENTORY if matches(i, c.constraints)])


@pytest.mark.parametrize("c", DATASET.cases, ids=lambda c: c.id)
def test_a_perfect_agent_passes_every_golden_case(c):
    """Guards against the dataset and the evaluator disagreeing."""
    assert evaluate_case(c, oracle_outcome(c), INVENTORY).passed
