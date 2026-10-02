"""Run the golden dataset through the agent and both evaluation layers."""

import argparse
import os
import statistics
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from travel_ai_eval.ai.prompts import PROMPT_VERSION
from travel_ai_eval.ai.provider import AnthropicProvider, LLMProvider
from travel_ai_eval.ai.travel_agent import TravelAgent, select_relevant_inventory
from travel_ai_eval.config import BASELINE_PATH, MissingAPIKeyError, load_settings
from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation.deterministic import (
    constraint_satisfaction_rate,
    evaluate_case,
    inventory_accuracy_rate,
    schema_validity_rate,
)
from travel_ai_eval.evaluation.groundedness import GROUNDEDNESS_PROMPT_VERSION, check_groundedness
from travel_ai_eval.evaluation.llm_judge import JUDGE_PROMPT_VERSION, judge_response
from travel_ai_eval.evaluation.thresholds import Thresholds, evaluate_gate
from travel_ai_eval.models.results import CaseResult, RunMetadata, RunMetrics, RunResult
from travel_ai_eval.models.schemas import (
    CheckResult,
    EvalResult,
    GoldenCase,
    InventoryItem,
)
from travel_ai_eval.reporting.report import (
    format_terminal_report,
    load_report,
    save_run_outputs,
    write_json_report,
)

ProgressCallback = Callable[[int, int, CaseResult], None]


def evaluate_one(
    case: GoldenCase,
    agent: TravelAgent,
    provider: LLMProvider,
    inventory: list[InventoryItem],
) -> CaseResult:
    outcome = agent.run(case.query)
    result = CaseResult(
        case_id=case.id,
        category=case.category,
        query=case.query,
        response=outcome.response,
        raw_output=outcome.raw_output,
        agent_error=outcome.error,
        deterministic=evaluate_case(case, outcome, inventory),
    )
    if outcome.response is None:
        return result  # nothing to judge; the failure is already recorded

    relevant = select_relevant_inventory(case.query, inventory)
    judged = judge_response(
        provider, case.query, case.constraints, relevant, outcome.response
    )
    result.judge, result.judge_error = judged.value, judged.error
    grounded = check_groundedness(provider, case.query, relevant, outcome.response)
    result.groundedness, result.groundedness_error = grounded.value, grounded.error
    return result


def _crashed(case: GoldenCase, exc: Exception) -> CaseResult:
    """Record an unexpected exception as a failed case so the rest of the run continues."""
    reason = f"{type(exc).__name__}: {exc}"
    return CaseResult(
        case_id=case.id,
        category=case.category,
        query=case.query,
        response=None,
        raw_output="",
        agent_error=f"runner_error: {reason}",
        deterministic=EvalResult(
            checks=[CheckResult(name="schema_validity", passed=False, reason=reason)]
        ),
    )


def _mean(values: list[int]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def compute_metrics(cases: list[CaseResult]) -> RunMetrics:
    det = [c.deterministic for c in cases]
    judged = [c.judge for c in cases if c.judge]
    grounded = [c.groundedness for c in cases if c.groundedness]
    return RunMetrics(
        schema_validity=schema_validity_rate(det),
        inventory_accuracy=inventory_accuracy_rate(det),
        constraint_satisfaction=constraint_satisfaction_rate(det),
        avg_relevance=_mean([j.relevance for j in judged]),
        avg_groundedness=_mean([g.score for g in grounded]),
        avg_helpfulness=_mean([j.helpfulness for j in judged]),
        avg_instruction_following=_mean([j.instruction_following for j in judged]),
        avg_judge_constraint_satisfaction=_mean(
            [j.constraint_satisfaction for j in judged]
        ),
        judge_scored_cases=len(judged),
        groundedness_scored_cases=len(grounded),
    )


def run_evaluation(
    provider: LLMProvider,
    inventory: list[InventoryItem],
    cases: list[GoldenCase],
    dataset_version: str,
    on_case: ProgressCallback | None = None,
    thresholds: Thresholds | None = None,
) -> RunResult:
    agent = TravelAgent(provider, inventory)
    results: list[CaseResult] = []
    for n, case in enumerate(cases, start=1):
        try:
            result = evaluate_one(case, agent, provider, inventory)
        except Exception as exc:  # one bad case must never abort the run
            result = _crashed(case, exc)
        results.append(result)
        if on_case:
            on_case(n, len(cases), result)
    metrics = compute_metrics(results)
    return RunResult(
        metadata=RunMetadata(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            model=provider.model,
            dataset_version=dataset_version,
            prompt_version=PROMPT_VERSION,
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            groundedness_prompt_version=GROUNDEDNESS_PROMPT_VERSION,
            total_cases=len(cases),
        ),
        metrics=metrics,
        gate=evaluate_gate(metrics, len(cases), thresholds or Thresholds.from_env()),
        cases=results,
    )


def _print_progress(n: int, total: int, r: CaseResult) -> None:
    status = "ok  " if r.deterministic.passed else "FAIL"
    print(f"[{n}/{total}] {status} {r.case_id}", file=sys.stderr, flush=True)


def _load_baseline(path: Path) -> RunResult | None:
    if not path.is_file():
        return None
    try:
        return load_report(path)
    except ValueError as e:  # pydantic.ValidationError is a ValueError
        print(f"Ignoring unreadable baseline {path}: {e}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the travel AI evaluation.")
    parser.add_argument(
        "--limit", type=int, help="only run the first N cases (cost control)"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="earlier run JSON to compare against (default: reports/baseline.json if present)",
    )
    parser.add_argument("--label", default=os.environ.get("EVAL_LABEL"),
                        help="short note stored with the run in the history (or set EVAL_LABEL)")
    args = parser.parse_args(argv)

    try:
        provider = AnthropicProvider(load_settings())
    except MissingAPIKeyError as e:
        print(e, file=sys.stderr)
        return 2
    dataset = load_dataset()
    cases = dataset.cases[: args.limit] if args.limit else dataset.cases
    run = run_evaluation(
        provider, load_inventory(), cases, dataset.version, _print_progress
    )
    print(format_terminal_report(run, _load_baseline(args.baseline)))
    if args.limit:
        print("\nPartial run (--limit): not added to the history.")
        print(f"JSON report: {write_json_report(run)}")
    else:
        paths = save_run_outputs(run, args.label)
        if "html" in paths:
            print(f"\nJSON report: {paths['json']}\nHTML trends: {paths['html']}")
        else:
            print(
                "\nRun NOT recorded in the history: every case failed with an API error "
                "(check ANTHROPIC_API_KEY, account credit and network). See the Failures above."
            )
    return 0 if run.gate.passed else 1


if __name__ == "__main__":
    sys.exit(main())
