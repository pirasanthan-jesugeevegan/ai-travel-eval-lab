import pytest

from travel_ai_eval.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from travel_ai_eval.ai.provider import AnthropicProvider, LLMError
from travel_ai_eval.ai.travel_agent import (
    TravelAgent,
    build_user_message,
    parse_response,
    select_relevant_inventory,
)
from travel_ai_eval.config import MissingAPIKeyError, Settings
from travel_ai_eval.data import load_inventory

INVENTORY = load_inventory()
GOOD = '{"answer": "ok", "recommendations": [{"hotel_id": "DXB001", "reason": "fits"}]}'


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


def test_select_by_destination_and_country():
    dubai = select_relevant_inventory("hotel in Dubai", INVENTORY)
    assert {i.destination for i in dubai} == {"Dubai"}
    spain = select_relevant_inventory("beach holiday in Spain", INVENTORY)
    assert {i.destination for i in spain} == {"Barcelona", "Tenerife"}


def test_select_falls_back_to_full_inventory():
    assert select_relevant_inventory("hotel on Mars", INVENTORY) == INVENTORY


def test_select_does_not_apply_budget_filter():
    dubai = select_relevant_inventory("Dubai under £500", INVENTORY)
    assert any(i.price_gbp > 500 for i in dubai)


def test_user_message_contains_query_and_ids():
    msg = build_user_message("find me a hotel", INVENTORY[:2])
    assert "find me a hotel" in msg and INVENTORY[0].id in msg


@pytest.mark.parametrize("text", [GOOD, f"```json\n{GOOD}\n```", f"Here you go: {GOOD} Enjoy!"])
def test_parse_response_tolerates_fences_and_prose(text):
    assert parse_response(text).recommendations[0].hotel_id == "DXB001"


@pytest.mark.parametrize("text", ["not json", '{"answer": "x"}', "{broken"])
def test_parse_response_rejects_bad_output(text):
    with pytest.raises(ValueError):
        parse_response(text)


def test_agent_success():
    provider = FakeProvider(GOOD)
    outcome = TravelAgent(provider, INVENTORY).run("Dubai please")
    assert outcome.error is None and outcome.response.recommendations
    assert provider.calls[0]["system"] == SYSTEM_PROMPT


def test_agent_records_llm_error_instead_of_raising():
    outcome = TravelAgent(FakeProvider(LLMError("rate limited")), INVENTORY).run("x")
    assert outcome.response is None and outcome.error.startswith("llm_error")


def test_agent_records_invalid_output_and_keeps_raw():
    outcome = TravelAgent(FakeProvider("sorry, no"), INVENTORY).run("x")
    assert outcome.response is None
    assert outcome.error.startswith("invalid_output") and outcome.raw_output == "sorry, no"


def test_prompt_is_versioned_and_states_key_rules():
    assert PROMPT_VERSION
    for phrase in ["Never invent", "empty recommendations", "Never reveal", "next step"]:
        assert phrase in SYSTEM_PROMPT


def test_provider_requires_api_key():
    with pytest.raises(MissingAPIKeyError):
        AnthropicProvider(Settings(api_key=None, model="m"))
