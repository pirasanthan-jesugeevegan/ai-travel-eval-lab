"""Central configuration, read from environment variables / .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5-5"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"


class MissingAPIKeyError(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is needed but not set."""


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str

    def require_api_key(self) -> str:
        if not self.api_key:
            raise MissingAPIKeyError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        return self.api_key


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL,
    )
