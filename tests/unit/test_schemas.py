import pytest
from pydantic import ValidationError

from travel_ai_eval.config import DEFAULT_MODEL, MissingAPIKeyError, load_settings
from travel_ai_eval.models.schemas import (
    Constraints,
    GoldenCase,
    InventoryItem,
    Recommendation,
    TravelResponse,
)

HOTEL = {
    "id": "DXB001",
    "name": "Dubai Beach Resort",
    "destination": "Dubai",
    "country": "United Arab Emirates",
    "price_gbp": 1750,
    "family_friendly": True,
    "free_cancellation": True,
    "beach_access": True,
    "rating": 4.5,
}


def test_inventory_item_valid():
    assert InventoryItem(**HOTEL).price_gbp == 1750


@pytest.mark.parametrize("field,value", [("price_gbp", 0), ("rating", 5.5), ("rating", -1)])
def test_inventory_item_rejects_out_of_range(field, value):
    with pytest.raises(ValidationError):
        InventoryItem(**{**HOTEL, field: value})


def test_travel_response_allows_empty_recommendations():
    r = TravelResponse(answer="Nothing suitable in the inventory.", recommendations=[])
    assert r.recommendations == []


def test_travel_response_parses_json():
    r = TravelResponse.model_validate_json(
        '{"answer": "x", "recommendations": [{"hotel_id": "DXB001", "reason": "y"}]}'
    )
    assert r.recommendations == [Recommendation(hotel_id="DXB001", reason="y")]


@pytest.mark.parametrize(
    "payload",
    [
        {"answer": "x"},  # missing recommendations
        {"answer": "x", "recommendations": [{"hotel_id": "A"}]},  # missing reason
        {"answer": "x", "recommendations": "DXB001"},  # wrong type
    ],
)
def test_travel_response_rejects_malformed(payload):
    with pytest.raises(ValidationError):
        TravelResponse.model_validate(payload)


def test_golden_case_defaults():
    case = GoldenCase(id="a-001", category="normal", query="hi")
    assert case.language == "en"
    assert case.constraints == Constraints()


def test_constraints_reject_non_positive_budget():
    with pytest.raises(ValidationError):
        Constraints(max_budget_gbp=0)


def test_settings_model_default_and_override(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert load_settings().model == DEFAULT_MODEL
    monkeypatch.setenv("ANTHROPIC_MODEL", "some-other-model")
    assert load_settings().model == "some-other-model"


def test_require_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("travel_ai_eval.config.load_dotenv", lambda: None)
    with pytest.raises(MissingAPIKeyError):
        load_settings().require_api_key()
