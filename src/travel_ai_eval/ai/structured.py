"""Shared helper: ask the model for JSON and validate it against a Pydantic model."""

import re
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from travel_ai_eval.ai.provider import LLMError, LLMProvider


@dataclass(frozen=True)
class Structured[T: BaseModel]:
    """A validated model reply, or the reason there isn't one. Never raises for model faults."""

    value: T | None
    raw_output: str
    error: str | None = None


def extract_json_object(text: str) -> str:
    """Strip markdown fences / surrounding prose and return the outermost {...} text."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return cleaned[start : end + 1]


def parse_model[T: BaseModel](text: str, schema: type[T]) -> T:
    return schema.model_validate_json(extract_json_object(text))


def generate_structured[T: BaseModel](
    provider: LLMProvider, *, system: str, user: str, schema: type[T], max_tokens: int = 4096
) -> Structured[T]:
    try:
        raw = provider.generate(system=system, user=user, max_tokens=max_tokens)
    except LLMError as e:
        return Structured(None, "", f"llm_error: {e}")
    try:
        return Structured(parse_model(raw, schema), raw)
    except (ValueError, ValidationError) as e:
        return Structured(None, raw, f"invalid_output: {e}")
