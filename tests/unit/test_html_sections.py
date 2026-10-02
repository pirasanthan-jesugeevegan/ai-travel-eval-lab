import pytest

from helpers import CASES, INVENTORY, ConstantAgentProvider, PerfectJudgeProvider
from travel_ai_eval.data import load_dataset
from travel_ai_eval.evaluation.runner import run_evaluation
from travel_ai_eval.reporting.history import summarise
from travel_ai_eval.reporting.html_report import render_html
from travel_ai_eval.reporting.html_sections import (
    CATEGORY_HELP,
    SECTION_INTRO,
    render_categories,
    render_gate_table,
    render_glossary,
    render_not_measured,
    render_summary,
)
from travel_ai_eval.reporting.metrics import METRICS


@pytest.fixture(scope="module")
def good():
    return summarise(run_evaluation(PerfectJudgeProvider(), INVENTORY, CASES, "v1"))


@pytest.fixture(scope="module")
def bad():
    ds = load_dataset()
    return summarise(run_evaluation(ConstantAgentProvider("NYC001"), INVENTORY, ds.cases, ds.version))


def test_every_section_has_an_intro_and_every_metric_an_explanation():
    assert {"gate", "trends", "categories", "runs", "configs", "stability", "failures",
            "unmeasured", "glossary"} <= set(SECTION_INTRO)
    assert all(m.meaning and m.kind in {"Rule-based", "LLM-judged"} for m in METRICS)


def test_page_has_all_sections_in_plain_language(good, bad):
    page = render_html([good, bad])
    for heading in ["How to read this page", "Quality gate: why PASS or FAIL", "Trends",
                    "Results by category", "What changed, run by run", "Results by configuration",
                    "Case stability", "Not measured yet", "What the metrics mean"]:
        assert heading in page, heading
    assert "Since the previous run:" in page  # plain-English summary compares with previous run


def test_single_run_explains_why_there_is_no_trend(good):
    page = render_html([good])
    assert "no trend to draw yet" in page and "first recorded run" in page


def test_gate_table_lists_every_check_with_a_result(good, bad):
    table = render_gate_table(bad)
    assert table.count("<tr>") == len(bad.gate.checks) + 1  # header + one row per check
    assert "✕ FAIL" in table and "Judge coverage" in table
    assert "✓ PASS" in render_gate_table(good)


def test_categories_show_pass_counts_and_change_vs_previous(good, bad):
    cats = render_categories([good, bad])
    assert "passed (latest run)" in cats.lower() or "Passed (latest run)" in cats
    assert "✕" in cats and "▼ worse" in cats
    assert any(CATEGORY_HELP[c] in render_categories([good]) for c in CATEGORY_HELP if c in
               {x.category for x in good.cases})
    assert "n/a" in render_categories([good])  # nothing to compare with


def test_unmeasured_items_are_honest_placeholders(good):
    page = render_not_measured([good])
    for item in ["Latency per reply", "Token usage and cost per run", "LLM judge vs human agreement"]:
        assert item in page
    assert page.count("Not measured yet") == 3
    assert "Not enough data" in page  # variance needs 3 runs of one configuration


def test_variance_placeholder_flips_once_there_are_three_matching_runs(good):
    runs = []
    for i in range(3):
        e = good.model_copy(deep=True)
        e.run_id = f"r{i}"
        runs.append(e)
    assert "Partly measured" in render_not_measured(runs)


def test_summary_is_plain_english_and_escaped(good, bad):
    text = render_summary([good, bad])
    assert "Run #2 tested" in text and "fell" in text
    assert "<" not in text.replace("<p class=\"summary\">", "").replace("</p>", "")


def test_glossary_lists_each_metric_once(good):
    g = render_glossary()
    for m in METRICS:
        assert g.count(f"<td>{m.label}</td>") == 1


def test_latest_failures_only_shown_when_they_belong_to_the_last_run(good):
    run = run_evaluation(ConstantAgentProvider("NYC001"), INVENTORY, load_dataset().cases, "v")
    assert "Failures in the latest run" in render_html([summarise(run)], run)
    other = run.model_copy(deep=True)
    other.metadata = other.metadata.model_copy(update={"timestamp": "2000-01-01T00:00:00+00:00"})
    assert "Failures in the latest run" not in render_html([summarise(run)], other)
