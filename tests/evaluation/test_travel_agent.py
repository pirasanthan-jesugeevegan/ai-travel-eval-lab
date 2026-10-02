"""AI evaluation suite. Makes real Anthropic calls (~3 per golden case).

Run explicitly:  pytest tests/evaluation -s
Skipped automatically when ANTHROPIC_API_KEY is not set.
"""

import os

import pytest

from travel_ai_eval.ai.provider import AnthropicProvider
from travel_ai_eval.config import BASELINE_PATH, load_settings
from travel_ai_eval.data import load_dataset, load_inventory
from travel_ai_eval.evaluation.runner import run_evaluation
from travel_ai_eval.reporting.report import (
    format_terminal_report,
    load_report,
    save_run_outputs,
)

pytestmark = pytest.mark.skipif(
    not load_settings().api_key,
    reason="ANTHROPIC_API_KEY not set - skipping AI evaluation (unit tests do not need it)",
)


@pytest.fixture(scope="module")
def report():
    dataset = load_dataset()
    run = run_evaluation(AnthropicProvider(load_settings()), load_inventory(), dataset.cases, dataset.version)
    save_run_outputs(run, os.environ.get("EVAL_LABEL"))
    baseline = load_report(BASELINE_PATH) if BASELINE_PATH.is_file() else None
    text = format_terminal_report(run, baseline)
    print("\n" + text)
    return run, text


def test_every_case_was_evaluated(report):
    run, _ = report
    assert len(run.cases) == run.metadata.total_cases == len(load_dataset().cases)


def test_schema_validity(report):
    run, text = report
    assert run.metrics.schema_validity == 1.0, text


def test_constraint_satisfaction(report):
    run, text = report
    assert run.gate.checks[1].passed, text


def test_quality_gate(report):
    run, text = report
    assert run.gate.passed, text
