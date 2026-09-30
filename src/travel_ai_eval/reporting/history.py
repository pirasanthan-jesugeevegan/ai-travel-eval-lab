"""Append-only run history (JSON Lines) so results can be compared and trended over time.

One line per full run: metadata, metrics, the gate result with the thresholds that applied,
and a compact per-case pass/fail summary. Full per-case detail stays in reports/latest.json.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError

from travel_ai_eval.config import PROJECT_ROOT, REPORTS_DIR
from travel_ai_eval.models.results import GateResult, RunMetadata, RunMetrics, RunResult

HISTORY_PATH = REPORTS_DIR / "history.jsonl"

# A change in any of these can move every metric, so runs are only strictly comparable
# when they match.
SIGNATURE_FIELDS = ("model", "prompt_version", "judge_prompt_version", "dataset_version")


class CaseSummary(BaseModel):
    case_id: str
    category: str
    passed: bool
    failed_checks: list[str]


class HistoryEntry(BaseModel):
    run_id: str
    label: str | None = None
    git_commit: str | None = None
    git_dirty: bool = False
    metadata: RunMetadata
    metrics: RunMetrics
    gate: GateResult
    cases: list[CaseSummary]

    @property
    def signature(self) -> tuple[str, ...]:
        return tuple(getattr(self.metadata, f) for f in SIGNATURE_FIELDS)


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_state() -> tuple[str | None, bool]:
    """Short commit hash and whether source files have uncommitted changes (reports/ ignored)."""
    commit = _git("rev-parse", "--short", "HEAD")
    status = _git("status", "--porcelain", "--", ".", ":!reports")
    return commit, bool(status)


def summarise(run: RunResult, label: str | None = None) -> HistoryEntry:
    commit, dirty = git_state()
    return HistoryEntry(
        run_id=f"{run.metadata.timestamp}|{run.metadata.model}",
        label=label,
        git_commit=commit,
        git_dirty=dirty,
        metadata=run.metadata,
        metrics=run.metrics,
        gate=run.gate,
        cases=[
            CaseSummary(
                case_id=c.case_id,
                category=c.category,
                passed=c.deterministic.passed,
                failed_checks=[k.name for k in c.deterministic.checks if not k.passed],
            )
            for c in run.cases
        ],
    )


def is_api_outage(run: RunResult) -> bool:
    """True when every case failed on the API call itself (bad key, no credit, network down).

    That says nothing about the travel agent's quality, so it must not enter the history
    as if it were an evaluation result.
    """
    return bool(run.cases) and all((c.agent_error or "").startswith("llm_error") for c in run.cases)


def load_history(path: Path = HISTORY_PATH) -> list[HistoryEntry]:
    if not path.is_file():
        return []
    entries = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(HistoryEntry.model_validate_json(line))
        except ValidationError:
            print(f"Skipping unreadable history line {n} in {path}", file=sys.stderr)
    return entries


def append_history(entry: HistoryEntry, path: Path = HISTORY_PATH) -> bool:
    """Append a run. Returns False (and writes nothing) if this run is already recorded."""
    if any(e.run_id == entry.run_id for e in load_history(path)):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
    return True


def changes_vs_previous(entries: list[HistoryEntry]) -> list[list[str]]:
    """For each run, which signature fields changed since the previous run (empty for the first)."""
    out: list[list[str]] = [[]]
    for prev, cur in zip(entries, entries[1:], strict=False):
        out.append(
            [
                f"{f}: {getattr(prev.metadata, f)} → {getattr(cur.metadata, f)}"
                for f in SIGNATURE_FIELDS
                if getattr(prev.metadata, f) != getattr(cur.metadata, f)
            ]
        )
    return out[: len(entries)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the run history.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add an existing run JSON (e.g. reports/baseline.json)")
    add.add_argument("path", type=Path)
    add.add_argument("--label", help="short note shown in the report")
    args = parser.parse_args(argv)

    run = RunResult.model_validate_json(args.path.read_text(encoding="utf-8"))
    entry = summarise(run, args.label)
    # The current checkout is not necessarily the code this run used, so don't claim it was.
    entry.git_commit, entry.git_dirty = None, False
    added = append_history(entry)
    print("added" if added else "already recorded", "-", args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
