"""Travel recommendation agent: select inventory -> ask the model -> validate."""

import json
from dataclasses import dataclass

from pydantic import ValidationError

from travel_ai_eval.ai.prompts import SYSTEM_PROMPT
from travel_ai_eval.ai.provider import LLMError, LLMProvider
from travel_ai_eval.ai.structured import parse_model
from travel_ai_eval.models.schemas import InventoryItem, TravelResponse


@dataclass(frozen=True)
class AgentOutcome:
    """Result of one agent call. Failures are data, not exceptions."""

    response: TravelResponse | None
    raw_output: str
    error: str | None = None


def select_relevant_inventory(query: str, inventory: list[InventoryItem]) -> list[InventoryItem]:
    """Deterministic filter: keep hotels whose destination or country is named in the query.

    Falls back to the whole (small) inventory when nothing is named, so the model - not
    this filter - decides what to say about unknown places. Constraints such as budget are
    deliberately NOT applied here: respecting them is the model behaviour under test.
    """
    q = query.lower()
    matched = [i for i in inventory if i.destination.lower() in q or i.country.lower() in q]
    return matched or inventory


def build_user_message(query: str, inventory: list[InventoryItem]) -> str:
    items = json.dumps([i.model_dump() for i in inventory], indent=1)
    return f"Inventory (JSON):\n{items}\n\nUser request:\n{query}"


def parse_response(text: str) -> TravelResponse:
    """Parse model text into TravelResponse. Tolerates markdown fences and surrounding prose."""
    return parse_model(text, TravelResponse)


class TravelAgent:
    def __init__(self, provider: LLMProvider, inventory: list[InventoryItem]) -> None:
        self._provider = provider
        self._inventory = inventory

    def run(self, query: str) -> AgentOutcome:
        relevant = select_relevant_inventory(query, self._inventory)
        try:
            raw = self._provider.generate(
                system=SYSTEM_PROMPT, user=build_user_message(query, relevant)
            )
        except LLMError as e:
            return AgentOutcome(None, "", f"llm_error: {e}")
        try:
            return AgentOutcome(parse_response(raw), raw)
        except (ValueError, ValidationError) as e:
            return AgentOutcome(None, raw, f"invalid_output: {e}")
