import pytest

from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation import runner
from travel_ai_eval.evaluation.runner import run_evaluation
from travel_ai_eval.evaluation.thresholds import Thresholds, evaluate_gate
from travel_ai_eval.models.results import RunMetrics

PERFECT = dict(
    schema_validity=1.0, inventory_accuracy=1.0, constraint_satisfaction=1.0,
    avg_relevance=5.0, avg_groundedness=5.0, avg_helpfulness=5.0,
    avg_instruction_following=5.0, avg_judge_constraint_satisfaction=5.0,
    judge_scored_cases=40, groundedness_scored_cases=40,
)


def gate(total=40, **overrides):
    return evaluate_gate(RunMetrics(**{**PERFECT, **overrides}), total, Thresholds())


def failed(result):
    return {c.name for c in result.checks if not c.passed}


def test_defaults_match_spec():
    t = Thresholds()
    assert (t.schema_validity, t.constraint_satisfaction) == (1.0, 0.95)
    assert (t.relevance, t.groundedness, t.helpfulness) == (4.3, 4.5, 4.3)


def test_all_good_passes():
    g = gate()
    assert g.passed and g.verdict == "PASS" and not failed(g)


@pytest.mark.parametrize(
    "override,name",
    [
        ({"schema_validity": 0.975}, "schema_validity"),
        ({"constraint_satisfaction": 0.9}, "constraint_satisfaction"),
        ({"avg_relevance": 4.2}, "relevance"),
        ({"avg_groundedness": 4.4}, "groundedness"),
        ({"avg_helpfulness": 4.29}, "helpfulness"),
        ({"judge_scored_cases": 30}, "judge_coverage"),
    ],
)
def test_each_threshold_fails_the_gate(override, name):
    g = gate(**override)
    assert not g.passed and g.verdict == "FAIL" and failed(g) == {name}


def test_boundaries_are_inclusive():
    assert gate(constraint_satisfaction=0.95, avg_relevance=4.3, avg_groundedness=4.5).passed


def test_perfect_llm_scores_cannot_override_deterministic_failure():
    g = gate(constraint_satisfaction=0.88)  # judge scores stay at 5.0
    assert not g.passed and failed(g) == {"constraint_satisfaction"}


def test_missing_metric_fails():
    g = gate(avg_relevance=None, judge_scored_cases=0)
    assert not g.passed and {"relevance", "judge_coverage"} <= failed(g)


def test_zero_cases_fails():
    assert not gate(total=0).passed


def test_thresholds_configurable_from_env(monkeypatch):
    monkeypatch.setenv("EVAL_MIN_HELPFULNESS", "4.0")
    monkeypatch.setenv("EVAL_MIN_CONSTRAINT_SATISFACTION", "0.8")
    t = Thresholds.from_env()
    assert t.helpfulness == 4.0 and t.constraint_satisfaction == 0.8 and t.relevance == 4.3
    assert evaluate_gate(RunMetrics(**{**PERFECT, "avg_helpfulness": 4.1}), 40, t).passed


def test_invalid_env_value_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("EVAL_MIN_RELEVANCE", "high")
    with pytest.raises(ValueError, match="EVAL_MIN_RELEVANCE"):
        Thresholds.from_env()


JUDGE_OK = ('{"relevance": 5, "groundedness": 5, "helpfulness": 5, '
            '"constraint_satisfaction": 5, "instruction_following": 5, "reason": "r"}')
GROUND_OK = '{"grounded": true, "score": 5, "unsupported_claims": [], "reason": "r"}'


class ConstantAgentProvider:
    """Fake model: a perfect-scoring judge, and an agent that always recommends one hotel."""

    model = "fake"

    def __init__(self, hotel_id: str) -> None:
        self.hotel_id = hotel_id

    def generate(self, *, system, user, max_tokens=4096):
        if "travel recommendation assistant" in system:
            return '{"answer": "a", "recommendations": [{"hotel_id": "%s", "reason": "r"}]}' % self.hotel_id
        return JUDGE_OK if "strict evaluator" in system else GROUND_OK


def test_regression_ignoring_constraints_fails_the_gate_despite_perfect_judge():
    """Simulates a prompt that ignores budget etc.: same hotel for everything."""
    ds = load_dataset()
    result = run_evaluation(ConstantAgentProvider("NYC001"), load_inventory(), ds.cases, ds.version)
    assert result.metrics.avg_relevance == 5.0
    assert result.metrics.constraint_satisfaction < 0.5
    assert not result.gate.passed


def test_main_returns_2_without_api_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("travel_ai_eval.config.load_dotenv", lambda: None)
    assert runner.main(["--limit", "1"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
