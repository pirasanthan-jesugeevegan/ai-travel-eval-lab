"""Central configuration, read from environment variables / .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5-5"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LATEST_PATH = REPORTS_DIR / "latest.json"  # most recent run, full detail (git-ignored)
BASELINE_PATH = REPORTS_DIR / "baseline.json"  # a known-good run to compare against
HISTORY_PATH = REPORTS_DIR / "history.jsonl"  # one summary line per run, for trends
HTML_PATH = REPORTS_DIR / "report.html"  # generated trend report


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
