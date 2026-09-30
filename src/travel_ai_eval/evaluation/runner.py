"""Run the golden dataset through the agent and both evaluation layers."""

import argparse
import statistics
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from travel_ai_eval.ai.prompts import PROMPT_VERSION
from travel_ai_eval.ai.provider import AnthropicProvider, LLMProvider
from travel_ai_eval.ai.travel_agent import AgentOutcome, TravelAgent, select_relevant_inventory
from travel_ai_eval.config import MissingAPIKeyError, load_settings
from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation.deterministic import (
    constraint_satisfaction_rate,
    evaluate_case,
    inventory_accuracy_rate,
    schema_validity_rate,
)
from travel_ai_eval.evaluation.groundedness import check_groundedness
from travel_ai_eval.evaluation.llm_judge import JUDGE_PROMPT_VERSION, judge_response
from travel_ai_eval.models.results import CaseResult, RunMetadata, RunMetrics, RunResult
from travel_ai_eval.models.schemas import (
    CheckResult,
    EvalResult,
    GoldenCase,
    InventoryItem,
)

ProgressCallback = Callable[[int, int, CaseResult], None]


def evaluate_one(
    case: GoldenCase, agent: TravelAgent, provider: LLMProvider, inventory: list[InventoryItem]
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
    judged = judge_response(provider, case.query, case.constraints, relevant, outcome.response)
    result.judge, result.judge_error = judged.value, judged.error
    grounded = check_groundedness(provider, case.query, relevant, outcome.response)
    result.groundedness, result.groundedness_error = grounded.value, grounded.error
    return result


def _crashed(case: GoldenCase, exc: Exception) -> CaseResult:
    reason = f"{type(exc).__name__}: {exc}"
    outcome = AgentOutcome(None, "", f"runner_error: {reason}")
    return CaseResult(
        case_id=case.id,
        category=case.category,
        query=case.query,
        response=None,
        raw_output="",
        agent_error=outcome.error,
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
        avg_judge_constraint_satisfaction=_mean([j.constraint_satisfaction for j in judged]),
        judge_scored_cases=len(judged),
        groundedness_scored_cases=len(grounded),
    )


def run_evaluation(
    provider: LLMProvider,
    inventory: list[InventoryItem],
    cases: list[GoldenCase],
    dataset_version: str,
    on_case: ProgressCallback | None = None,
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
    return RunResult(
        metadata=RunMetadata(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            model=provider.model,
            dataset_version=dataset_version,
            prompt_version=PROMPT_VERSION,
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            total_cases=len(cases),
        ),
        metrics=compute_metrics(results),
        cases=results,
    )


def _print_progress(n: int, total: int, r: CaseResult) -> None:
    status = "ok  " if r.deterministic.passed else "FAIL"
    print(f"[{n}/{total}] {status} {r.case_id}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the travel AI evaluation.")
    parser.add_argument("--limit", type=int, help="only run the first N cases (cost control)")
    args = parser.parse_args(argv)

    try:
        provider = AnthropicProvider(load_settings())
    except MissingAPIKeyError as e:
        print(e, file=sys.stderr)
        return 2
    dataset = load_dataset()
    cases = dataset.cases[: args.limit] if args.limit else dataset.cases
    run = run_evaluation(provider, load_inventory(), cases, dataset.version, _print_progress)
    print(run.metrics.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
