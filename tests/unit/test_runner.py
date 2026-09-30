from helpers import CASES, INVENTORY, ScriptedProvider
from travel_ai_eval.ai.provider import LLMError
from travel_ai_eval.data import load_dataset
from travel_ai_eval.evaluation.runner import compute_metrics, run_evaluation


def run(provider, cases=CASES):
    return run_evaluation(provider, INVENTORY, cases, "v-test")


def test_happy_path_metrics_and_metadata():
    p = ScriptedProvider()
    result = run(p)
    m, meta = result.metrics, result.metadata
    assert (m.schema_validity, m.inventory_accuracy, m.constraint_satisfaction) == (1, 1, 1)
    assert m.avg_relevance == 4 and m.avg_groundedness == 5 and m.avg_instruction_following == 3
    assert m.judge_scored_cases == 3
    assert meta.model == "fake-model" and meta.dataset_version == "v-test"
    assert meta.total_cases == 3 and meta.prompt_version and meta.timestamp
    assert p.calls == {"agent": 3, "judge": 3, "ground": 3}  # exactly one call of each per case


def test_agent_failure_is_recorded_and_not_judged_and_run_continues():
    p = ScriptedProvider({"Paris": "not json"})
    result = run(p)
    bad = next(c for c in result.cases if c.case_id == "ok-2")
    assert bad.response is None and bad.agent_error.startswith("invalid_output")
    assert not bad.deterministic.passed and bad.judge is None
    assert p.calls["judge"] == 2 and len(result.cases) == 3
    assert result.metrics.schema_validity == 2 / 3


def test_api_failure_for_one_case_does_not_stop_the_run():
    result = run(ScriptedProvider({"Rome": LLMError("rate limited")}))
    assert [c.deterministic.passed for c in result.cases] == [True, True, False]
    assert result.cases[2].agent_error.startswith("llm_error")


def test_unexpected_exception_is_contained():
    result = run(ScriptedProvider({"Paris": RuntimeError("bug")}))
    crashed = next(c for c in result.cases if c.case_id == "ok-2")
    assert crashed.agent_error.startswith("runner_error") and "bug" in crashed.agent_error
    assert not crashed.deterministic.passed
    assert sum(c.deterministic.passed for c in result.cases) == 2


def test_judge_failure_is_recorded_without_failing_deterministic():
    class BadJudge(ScriptedProvider):
        def generate(self, *, system, user, max_tokens=4096):
            if "strict evaluator" in system:
                return "garbage"
            return super().generate(system=system, user=user, max_tokens=max_tokens)

    result = run(BadJudge())
    assert all(c.judge is None and c.judge_error for c in result.cases)
    assert all(c.deterministic.passed for c in result.cases)
    assert result.metrics.avg_relevance is None and result.metrics.judge_scored_cases == 0


def test_progress_callback_and_result_serialises():
    seen = []
    result = run_evaluation(ScriptedProvider(), INVENTORY, CASES, "v", lambda n, t, r: seen.append((n, t)))
    assert seen == [(1, 3), (2, 3), (3, 3)]
    assert result.model_dump_json()


def test_compute_metrics_empty():
    assert compute_metrics([]).constraint_satisfaction == 0.0


def test_full_golden_dataset_runs_offline_with_fake_provider():
    ds = load_dataset()
    result = run_evaluation(ScriptedProvider(), INVENTORY, ds.cases, ds.version)
    assert result.metadata.total_cases == len(ds.cases) == len(result.cases)
    assert result.gate.verdict in {"PASS", "FAIL"}
