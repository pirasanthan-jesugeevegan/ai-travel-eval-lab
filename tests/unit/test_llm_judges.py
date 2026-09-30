import pytest

from travel_ai_eval.ai.provider import LLMError
from travel_ai_eval.ai.structured import extract_json_object, generate_structured
from travel_ai_eval.data import load_inventory
from travel_ai_eval.evaluation.groundedness import build_groundedness_message, check_groundedness
from travel_ai_eval.evaluation.llm_judge import build_judge_message, judge_response
from travel_ai_eval.models.schemas import (
    Constraints,
    JudgeScores,
    Recommendation,
    TravelResponse,
)

INVENTORY = load_inventory()[:2]
RESPONSE = TravelResponse(
    answer="Dubai Beach Resort fits.",
    recommendations=[Recommendation(hotel_id="DXB001", reason="family friendly")],
)
CONSTRAINTS = Constraints(destination="Dubai", max_budget_gbp=2000)
GOOD_SCORES = (
    '{"relevance": 5, "groundedness": 4, "helpfulness": 4, '
    '"constraint_satisfaction": 5, "instruction_following": 5, "reason": "ok"}'
)


class FakeProvider:
    model = "fake"

    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def generate(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append({"system": system, "user": user})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_judge_parses_valid_scores_with_one_call():
    p = FakeProvider(f"```json\n{GOOD_SCORES}\n```")
    out = judge_response(p, "q", CONSTRAINTS, INVENTORY, RESPONSE)
    assert out.error is None and out.value.relevance == 5
    assert len(p.calls) == 1


@pytest.mark.parametrize(
    "reply",
    [
        GOOD_SCORES.replace('"relevance": 5', '"relevance": 6'),
        GOOD_SCORES.replace('"relevance": 5', '"relevance": 0'),
        GOOD_SCORES.replace('"relevance": 5,', ""),
        "I think it's great",
    ],
)
def test_judge_rejects_invalid_output_without_raising(reply):
    out = judge_response(FakeProvider(reply), "q", CONSTRAINTS, INVENTORY, RESPONSE)
    assert out.value is None and out.error.startswith("invalid_output")


def test_judge_records_api_failure():
    out = judge_response(FakeProvider(LLMError("boom")), "q", CONSTRAINTS, INVENTORY, RESPONSE)
    assert out.value is None and out.error.startswith("llm_error")


def test_judge_message_has_inputs_but_no_expected_outcome():
    msg = build_judge_message("my query", CONSTRAINTS, INVENTORY, RESPONSE)
    assert "my query" in msg and "max_budget_gbp" in msg and INVENTORY[0].id in msg
    assert "DXB001" in msg and "null" not in msg  # unspecified constraints omitted
    for leak in ["expect_no", "category", "hallucination", "prompt_injection"]:
        assert leak not in msg


def test_groundedness_parses_verdict():
    reply = ('{"grounded": false, "score": 2, "unsupported_claims": '
             '["The hotel has a Michelin-starred restaurant."], "reason": "no evidence"}')
    out = check_groundedness(FakeProvider(reply), "q", INVENTORY, RESPONSE)
    assert out.value.grounded is False
    assert out.value.unsupported_claims == ["The hotel has a Michelin-starred restaurant."]


def test_groundedness_rejects_out_of_range_score():
    reply = '{"grounded": true, "score": 9, "unsupported_claims": [], "reason": "x"}'
    assert check_groundedness(FakeProvider(reply), "q", INVENTORY, RESPONSE).error


def test_groundedness_message_includes_inventory_and_response():
    msg = build_groundedness_message("q", INVENTORY, RESPONSE)
    assert "<inventory>" in msg and "Dubai Beach Resort fits." in msg


def test_extract_json_object_and_generic_helper():
    assert extract_json_object('noise {"a": 1} tail') == '{"a": 1}'
    with pytest.raises(ValueError):
        extract_json_object("nothing")
    assert generate_structured(
        FakeProvider(GOOD_SCORES), system="s", user="u", schema=JudgeScores
    ).value.reason == "ok"
