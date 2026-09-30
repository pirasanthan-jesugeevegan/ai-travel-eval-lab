import json

import pytest

from helpers import CASES, INVENTORY, ConstantAgentProvider, PerfectJudgeProvider
from travel_ai_eval.data import load_dataset
from travel_ai_eval.evaluation.runner import run_evaluation
from travel_ai_eval.reporting.history import (
    append_history,
    changes_vs_previous,
    is_api_outage,
    load_history,
    summarise,
)
from travel_ai_eval.reporting.html_report import render_html, write_html_report
from travel_ai_eval.reporting.report import save_run_outputs


@pytest.fixture(scope="module")
def good_run():
    return run_evaluation(PerfectJudgeProvider(), INVENTORY, CASES, "v1")


@pytest.fixture(scope="module")
def bad_run():
    ds = load_dataset()
    return run_evaluation(ConstantAgentProvider("NYC001"), INVENTORY, ds.cases, ds.version)


def entry(run, label=None, **meta):
    e = summarise(run, label)
    e.metadata = e.metadata.model_copy(update=meta)
    e.run_id = f"{e.metadata.timestamp}|{e.metadata.model}|{meta}"
    return e


def test_summary_keeps_metrics_gate_and_failed_checks(bad_run):
    e = summarise(bad_run, "regression")
    assert e.label == "regression" and e.metrics == bad_run.metrics
    assert e.gate.passed is False and len(e.cases) == len(bad_run.cases)
    failing = [c for c in e.cases if not c.passed]
    assert failing and all(c.failed_checks for c in failing)


def test_append_and_load_round_trip_and_dedupe(tmp_path, good_run):
    path = tmp_path / "h" / "history.jsonl"
    e = summarise(good_run, "first")
    assert append_history(e, path) is True
    assert append_history(e, path) is False  # same run is not recorded twice
    loaded = load_history(path)
    assert len(loaded) == 1 and loaded[0] == e


def test_load_history_missing_file_and_bad_lines(tmp_path, good_run, capsys):
    assert load_history(tmp_path / "none.jsonl") == []
    path = tmp_path / "history.jsonl"
    append_history(summarise(good_run), path)
    with path.open("a") as f:
        f.write("not json\n\n" + json.dumps({"run_id": "x"}) + "\n")
    assert len(load_history(path)) == 1
    assert "Skipping unreadable history line" in capsys.readouterr().err


def test_changes_between_runs_are_listed(good_run):
    a = entry(good_run)
    b = entry(good_run, prompt_version="2.0.0", timestamp="2030-01-01T00:00:00+00:00")
    c = entry(good_run, prompt_version="2.0.0", model="other", timestamp="2030-01-02T00:00:00+00:00")
    assert changes_vs_previous([a, b, c]) == [
        [],
        [f"prompt_version: {a.metadata.prompt_version} → 2.0.0"],
        [f"model: {a.metadata.model} → other"],
    ]
    assert changes_vs_previous([]) == []


def test_html_empty_history_explains_how_to_start():
    page = render_html([])
    assert "No runs recorded yet" in page and "<svg" not in page


def test_html_single_run_renders(good_run):
    page = render_html([summarise(good_run)])
    assert "QUALITY GATE: PASS" in page and page.count("<svg") == 6
    assert "first recorded run" in page


def test_html_regression_shows_fail_marker_delta_and_changes(good_run, bad_run):
    baseline = entry(good_run, "baseline")
    regressed = entry(bad_run, "regressed", prompt_version="9.9.9",
                      timestamp="2031-01-01T00:00:00+00:00")
    page = render_html([baseline, regressed], bad_run)
    assert "QUALITY GATE: FAIL" in page and "Below threshold" in page
    assert "<polygon" in page  # diamond marker for the run below threshold
    assert "▼" in page and "vs previous run" in page
    assert 'class="chg"' in page  # version-change hairline in the chart / bold cell in table
    assert "Changed: prompt_version" in page
    assert "budget_compliance" in page  # failure list from the latest full run
    assert "Case stability" in page and "Results by configuration" in page


def test_html_config_table_shows_spread_for_repeated_config(good_run):
    a = entry(good_run, timestamp="2030-01-01T00:00:00+00:00")
    b = entry(good_run, timestamp="2030-01-02T00:00:00+00:00")
    b.metrics = b.metrics.model_copy(update={"avg_relevance": 4.0})
    page = render_html([a, b])
    assert "(4.00–" in page  # min–max range shown for a configuration with 2 runs


def test_html_escapes_untrusted_text(good_run):
    page = render_html([summarise(good_run, '<script>alert(1)</script>"><img src=x>')])
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("<script>") == 1  # only the report's own script


def test_html_is_self_contained(good_run):
    page = render_html([summarise(good_run)])
    assert "http://" not in page and "https://" not in page
    assert "<link" not in page and "src=" not in page


def test_write_html_report_reads_history_and_latest(tmp_path, good_run):
    history = tmp_path / "history.jsonl"
    latest = tmp_path / "latest.json"
    append_history(summarise(good_run, "x"), history)
    latest.write_text(good_run.model_dump_json())
    out = write_html_report(history, latest, tmp_path / "out" / "report.html")
    assert "Travel AI evaluation: trends" in out.read_text()


def test_save_run_outputs_writes_json_history_and_html(tmp_path, good_run):
    paths = save_run_outputs(good_run, "lbl", out_dir=tmp_path)
    assert all(p.is_file() for p in paths.values())
    assert load_history(paths["history"])[0].label == "lbl"
    save_run_outputs(good_run, "lbl", out_dir=tmp_path)  # same run again: history unchanged
    assert len(load_history(paths["history"])) == 1


def test_api_outage_run_is_not_recorded(tmp_path):
    class DownProvider:
        model = "fake"

        def generate(self, **_):
            from travel_ai_eval.ai.provider import LLMError

            raise LLMError("credit balance is too low")

    run = run_evaluation(DownProvider(), INVENTORY, CASES, "v1")
    assert is_api_outage(run)
    paths = save_run_outputs(run, out_dir=tmp_path)
    assert set(paths) == {"json"} and not (tmp_path / "history.jsonl").exists()


def test_partial_api_failure_is_still_recorded(tmp_path, good_run):
    assert not is_api_outage(good_run)
