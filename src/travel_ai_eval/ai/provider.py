"""LLM provider abstraction. Anthropic is the only implementation."""

from typing import Protocol

import anthropic

from travel_ai_eval.config import Settings

REQUEST_TIMEOUT_S = 60.0


class LLMError(RuntimeError):
    """Any failure to obtain usable text from the model (API error, refusal, truncation)."""


class LLMProvider(Protocol):
    model: str

    def generate(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        """Return the model's text reply, or raise LLMError."""
        ...


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.model
        # The SDK already retries 429/5xx/connection errors with backoff (max_retries=2).
        self._client = anthropic.Anthropic(
            api_key=settings.require_api_key(), timeout=REQUEST_TIMEOUT_S
        )

    def generate(self, *, system: str, user: str, max_tokens: int = 4096) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "low"},  # keep eval runs cheap and fast
            )
        except anthropic.APITimeoutError as e:
            raise LLMError(f"Anthropic request timed out: {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMError(f"Anthropic rate limit exceeded after retries: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Anthropic connection error: {e}") from e

        if response.stop_reason == "refusal":
            raise LLMError("Model refused the request (stop_reason=refusal)")
        if response.stop_reason == "max_tokens":
            raise LLMError("Model output truncated (stop_reason=max_tokens)")
        text = "".join(b.text for b in response.content if b.type == "text")
        if not text.strip():
            raise LLMError("Model returned no text")
        return text
