from collections import Counter

import pytest

from helpers import matches
from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.models.schemas import GoldenCase

INVENTORY = load_inventory()
DATASET = load_dataset()

FEASIBLE_CATEGORIES = {"normal", "budget", "attribute", "multi_constraint", "ambiguous"}
INFEASIBLE_CATEGORIES = {"conflicting", "impossible"}


def test_inventory_size_and_coverage():
    assert 15 <= len(INVENTORY) <= 25
    destinations = {i.destination for i in INVENTORY}
    assert {
        "Dubai",
        "Paris",
        "Barcelona",
        "Tenerife",
        "Bangkok",
        "Phuket",
        "Rome",
        "New York",
        "Abu Dhabi",
    } <= destinations


def test_inventory_ids_unique():
    assert len({i.id for i in INVENTORY}) == len(INVENTORY)


def test_dataset_size_and_version():
    assert 40 <= len(DATASET.cases) <= 70
    assert DATASET.version


def test_dataset_covers_all_categories_and_is_not_all_happy_path():
    counts = Counter(c.category for c in DATASET.cases)
    assert set(counts) == set(GoldenCase.model_fields["category"].annotation.__args__)
    assert counts["multi_constraint"] >= 5
    assert counts["prompt_injection"] >= 2
    assert sum(1 for c in DATASET.cases if c.expect_no_recommendations) >= 5


def test_dataset_has_non_english_cases():
    assert {c.language for c in DATASET.cases} > {"en"}


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET.cases if c.category in FEASIBLE_CATEGORIES],
    ids=lambda c: c.id,
)
def test_feasible_cases_have_an_answer_in_inventory(case):
    assert any(matches(i, case.constraints) for i in INVENTORY)
    assert not case.expect_no_recommendations


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET.cases if c.category in INFEASIBLE_CATEGORIES],
    ids=lambda c: c.id,
)
def test_infeasible_cases_have_no_answer_in_inventory(case):
    assert not any(matches(i, case.constraints) for i in INVENTORY)
    assert case.expect_no_recommendations


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_inventory(tmp_path / "nope.json")


def test_duplicate_inventory_ids_rejected(tmp_path):
    item = INVENTORY[0].model_dump_json()
    f = tmp_path / "inv.json"
    f.write_text(f"[{item},{item}]")
    with pytest.raises(ValueError, match="Duplicate"):
        load_inventory(f)


def test_duplicate_case_ids_rejected(tmp_path):
    case = DATASET.cases[0].model_dump_json()
    f = tmp_path / "ds.json"
    f.write_text(f'{{"version": "x", "cases": [{case},{case}]}}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(f)


@pytest.mark.parametrize(
    "case",
    [c for c in DATASET.cases if c.category == "prompt_injection" and not c.expect_no_recommendations],
    ids=lambda c: c.id,
)
def test_injection_cases_that_expect_recommendations_are_feasible(case):
    assert any(matches(i, case.constraints) for i in INVENTORY)


def test_adversarial_coverage():
    ids = {c.id for c in DATASET.cases}
    assert {"injection-secret-001", "injection-repeat-001", "trap-fake-inventory-001"} <= ids
    assert any(c.forbidden_phrases for c in DATASET.cases)
    assert any(c.language != "en" and c.category == "prompt_injection" for c in DATASET.cases)


@pytest.mark.parametrize("case", [c for c in DATASET.cases if c.required_hotel_ids], ids=lambda c: c.id)
def test_required_hotels_exist_and_satisfy_the_constraints(case):
    by_id = {i.id: i for i in INVENTORY}
    for hotel_id in case.required_hotel_ids:
        assert hotel_id in by_id
        assert matches(by_id[hotel_id], case.constraints)
    assert not case.expect_no_recommendations
