import pytest
from test_runner import CASES, ScriptedProvider
from test_thresholds import JUDGE_OK, ConstantAgentProvider

from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation.runner import run_evaluation
from travel_ai_eval.reporting.report import (
    compare_runs,
    format_terminal_report,
    load_report,
    write_json_report,
)

INVENTORY = load_inventory()


class PerfectJudgeProvider(ScriptedProvider):
    """Sensible agent answers, judge scores all 5."""

    def generate(self, *, system, user, max_tokens=4096):
        if "strict evaluator" in system:
            return JUDGE_OK
        return super().generate(system=system, user=user, max_tokens=max_tokens)


@pytest.fixture(scope="module")
def good_run():
    return run_evaluation(PerfectJudgeProvider(), INVENTORY, CASES, "v1")


@pytest.fixture(scope="module")
def bad_run():
    ds = load_dataset()
    return run_evaluation(ConstantAgentProvider("NYC001"), INVENTORY, ds.cases, ds.version)


def test_passing_report_layout(good_run):
    text = format_terminal_report(good_run)
    for expected in [
        "Travel AI Evaluation", "Dataset: 3 cases", "Model: fake-model",
        "Deterministic Evaluation", "Schema validity:", "Constraint satisfaction:",
        "Inventory accuracy:", "LLM Evaluation", "Relevance:", "Groundedness:",
        "Helpfulness:", "Instruction following:", "Quality Gates",
        "Constraints >= 95%", "Groundedness >= 4.5", "QUALITY GATE: PASS",
    ]:
        assert expected in text, expected
    assert "Failures" not in text and "Comparison" not in text


def test_failing_report_is_actionable(bad_run):
    text = format_terminal_report(bad_run)
    assert "QUALITY GATE: FAIL" in text
    assert "Failures" in text
    assert "[budget_compliance]" in text and "NYC001" in text  # names case, check, reason


def test_gate_lines_show_pass_and_fail(bad_run):
    lines = {ln.split(">=")[0].strip(): ln for ln in format_terminal_report(bad_run).splitlines() if ">=" in ln}
    assert lines["Constraints"].rstrip().endswith("FAIL")
    assert lines["Relevance"].rstrip().endswith("PASS")


def test_comparison_shows_regression_arrows(good_run, bad_run):
    text = format_terminal_report(bad_run, baseline=good_run)
    row = next(ln for ln in text.splitlines() if ln.startswith("Constraint satisfaction") and "↓" in ln)
    assert "100.0%" in row
    assert "Note - runs differ in" in text and "dataset_version: v1 ->" in text


def test_compare_runs_directions(good_run, bad_run):
    deltas = {d.label: d for d in compare_runs(good_run, bad_run)}
    assert deltas["Constraint satisfaction"].direction == "↓"
    assert deltas["Relevance"].direction == ""  # unchanged within tolerance
    assert {d.direction for d in compare_runs(bad_run, good_run)} >= {"↑"}


def test_json_report_round_trip(tmp_path, good_run):
    path = write_json_report(good_run, tmp_path / "nested" / "latest.json")
    loaded = load_report(path)
    assert loaded == good_run
    assert loaded.metadata.model == "fake-model" and loaded.gate.passed


def test_load_report_rejects_garbage(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    with pytest.raises(ValueError):
        load_report(f)
