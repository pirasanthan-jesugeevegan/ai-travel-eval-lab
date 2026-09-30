from travel_ai_eval.data import load_inventory
from travel_ai_eval.models.schemas import Constraints, GoldenCase, InventoryItem


def matches(item: InventoryItem, c: Constraints) -> bool:
    """Independent oracle used by tests to cross-check the real evaluator."""
    return (
        (c.destination is None or item.destination == c.destination)
        and (c.country is None or item.country == c.country)
        and (c.max_budget_gbp is None or item.price_gbp <= c.max_budget_gbp)
        and (c.family_friendly is None or item.family_friendly == c.family_friendly)
        and (c.free_cancellation is None or item.free_cancellation == c.free_cancellation)
        and (c.beach_access is None or item.beach_access == c.beach_access)
        and (c.min_rating is None or item.rating >= c.min_rating)
    )


# --- shared fakes: offline stand-ins for the model -------------------------------------

INVENTORY = load_inventory()
CASES = [
    GoldenCase(id="ok-1", category="normal", query="Dubai please",
               constraints={"destination": "Dubai"}),
    GoldenCase(id="ok-2", category="normal", query="Paris please",
               constraints={"destination": "Paris"}),
    GoldenCase(id="ok-3", category="normal", query="Rome please",
               constraints={"destination": "Rome"}),
]
AGENT_OK = '{"answer": "a", "recommendations": [{"hotel_id": "%s", "reason": "r"}]}'
JUDGE_MIXED = ('{"relevance": 4, "groundedness": 4, "helpfulness": 5, '
               '"constraint_satisfaction": 5, "instruction_following": 3, "reason": "r"}')
JUDGE_PERFECT = ('{"relevance": 5, "groundedness": 5, "helpfulness": 5, '
                 '"constraint_satisfaction": 5, "instruction_following": 5, "reason": "r"}')
GROUND_OK = '{"grounded": true, "score": 5, "unsupported_claims": [], "reason": "r"}'


class ScriptedProvider:
    """Routes by system prompt: agent / judge / groundedness. `behaviour` may override per query."""

    model = "fake-model"

    def __init__(self, behaviour=None) -> None:
        self.behaviour = behaviour or {}
        self.calls = {"agent": 0, "judge": 0, "ground": 0}

    def generate(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        if "travel recommendation assistant" in system:
            self.calls["agent"] += 1
            for key, reply in self.behaviour.items():
                if key in user:
                    if isinstance(reply, Exception):
                        raise reply
                    return reply
            hotel = next(h.id for h in INVENTORY if h.destination in user)
            return AGENT_OK % hotel
        if "strict evaluator" in system:
            self.calls["judge"] += 1
            return JUDGE_MIXED
        self.calls["ground"] += 1
        return GROUND_OK


class PerfectJudgeProvider(ScriptedProvider):
    """Sensible agent answers, judge scores all 5."""

    def generate(self, *, system, user, max_tokens=4096):
        if "strict evaluator" in system:
            return JUDGE_PERFECT
        return super().generate(system=system, user=user, max_tokens=max_tokens)


class ConstantAgentProvider:
    """Fake model: a perfect-scoring judge, and an agent that always recommends one hotel."""

    model = "fake"

    def __init__(self, hotel_id: str) -> None:
        self.hotel_id = hotel_id

    def generate(self, *, system, user, max_tokens=4096):
        if "travel recommendation assistant" in system:
            return AGENT_OK % self.hotel_id
        return JUDGE_PERFECT if "strict evaluator" in system else GROUND_OK
