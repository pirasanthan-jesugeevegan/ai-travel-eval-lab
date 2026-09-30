from travel_ai_eval.models.schemas import Constraints, InventoryItem


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
