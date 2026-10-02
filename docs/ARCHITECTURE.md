# Architecture and code walkthrough

How the evaluation framework is built, why it is built that way, and where to look for each concern. For the project overview, results and limitations see the [README](../README.md).

**Contents**
1. [Design principles](#1-design-principles)
2. [System overview](#2-system-overview)
3. [Life of one test case](#3-life-of-one-test-case)
4. [The evaluation model](#4-the-evaluation-model)
5. [Module reference](#5-module-reference)
6. [Testing strategy](#6-testing-strategy)
7. [Reproducibility and versioning](#7-reproducibility-and-versioning)
8. [Extending the framework](#8-extending-the-framework)
9. [Design decisions and trade-offs](#9-design-decisions-and-trade-offs)
10. [Terms](#10-terms)

---

## 1. Design principles

| Principle | How it shows up in the code |
|---|---|
| **Facts are checked by code, not by a model** | Price, destination, hotel existence and amenities are compared in plain Python (`evaluation/deterministic.py`). No LLM is involved. |
| **A judge can never override a hard failure** | `EvalResult.passed` is true only if every deterministic check passes. The quality gate requires *every* threshold; one strong score cannot offset a failing one. |
| **Subjective qualities get an LLM judge, with guard rails** | Relevance, helpfulness and groundedness are scored 1-5 by a second model that never sees the expected outcome and treats the reply as untrusted data. |
| **Failures are data, not exceptions** | API errors, malformed JSON and unexpected exceptions are recorded against the case and the run continues. |
| **Everything that can move a result is recorded** | Model, agent prompt, judge prompt, groundedness prompt, dataset version, git commit and label are stored with every run. |
| **Offline by default** | Unit tests use fake providers and make no API calls. The paid evaluation is an explicit action. |
| **The model provider is an interface** | `LLMProvider` is a `Protocol`; `AnthropicProvider` is the only implementation. |
| **Small modules** | No file exceeds roughly 270 lines; each has one responsibility. |

---

## 2. System overview

```
 data/golden_dataset.json            data/travel_inventory.json
 (versioned test cases)              (synthetic source of truth)
            │                                    │
            └─────────────────┬──────────────────┘
                              ▼
                  evaluation/runner.py
                              │  per case
                              ▼
        ai/travel_agent.py ──► ai/provider.py ──► Anthropic API
        select inventory       (only module that
        build prompt, parse     talks to the API)
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
   evaluation/deterministic.py        evaluation/llm_judge.py
   (code checks, hard constraints)    evaluation/groundedness.py
              │                       (LLM-scored, subjective)
              └───────────────┬────────────────┘
                              ▼
                  runner.compute_metrics
                              ▼
                  evaluation/thresholds.py   ──►  PASS / FAIL  ──►  exit code 0 / 1
                              ▼
        reporting/  terminal report · latest.json · history.jsonl · report.html
```

Repository layout:

```
data/                   golden_dataset.json, travel_inventory.json
src/travel_ai_eval/
  config.py             settings, file paths, API key access
  data.py               load and validate the JSON inputs
  models/               schemas.py (inputs/outputs), results.py (run results)
  ai/                   prompts.py, provider.py, structured.py, travel_agent.py
  evaluation/           deterministic.py, llm_judge.py, groundedness.py,
                        thresholds.py, runner.py
  reporting/            metrics.py, report.py, history.py,
                        html_report.py, html_sections.py, html_tables.py,
                        html_common.py, html_assets.py
tests/unit/             offline tests
tests/evaluation/       the paid evaluation suite
reports/                history.jsonl and baseline.json (tracked), other outputs ignored
.github/workflows/      CI
```

---

## 3. Life of one test case

Example case: *"I want a family holiday in Dubai under £2000."* with expected constraints `destination=Dubai`, `max_budget_gbp=2000`, `family_friendly=true`.

1. `runner.run_evaluation` iterates over the cases and calls `evaluate_one`.
2. `travel_agent.select_relevant_inventory` keeps the hotels whose destination or country is named in the query (the four Dubai hotels). Budget is deliberately **not** filtered here: respecting it is the behaviour under test.
3. `TravelAgent.run` builds the user message (inventory JSON plus the query) and calls the provider with `SYSTEM_PROMPT`.
4. `AnthropicProvider.generate` calls the API and returns text, or raises `LLMError` for any failure (timeout, rate limit, API error, refusal, truncation, empty reply).
5. `parse_response` extracts the JSON and validates it into a `TravelResponse`. Failure becomes `AgentOutcome(error="invalid_output: ...")`.
6. `deterministic.evaluate_case` runs the checks and returns an `EvalResult`: schema, hotel-ID existence, destination, budget, family-friendly, presence of a recommendation, prompt-leak, secret exposure.
7. If the reply was valid, `llm_judge.judge_response` and `groundedness.check_groundedness` each make one API call.
8. The pieces are assembled into a `CaseResult`.
9. After the last case, `compute_metrics` aggregates and `thresholds.evaluate_gate` produces the verdict.
10. `reporting` writes the outputs, and `runner.main` exits `0` (PASS), `1` (FAIL) or `2` (no API key).

A case makes at most three API calls (agent, judge, groundedness). Invalid replies skip the two judge calls.

---

## 4. The evaluation model

### Layers

| Layer | Decides | Produced by | Gated? |
|---|---|---|---|
| Schema validity | Is the reply valid JSON of the required shape? | Code | Yes (100%) |
| Constraint satisfaction | Did every deterministic check pass for the case? | Code | Yes (≥ 95%) |
| Inventory accuracy | Do all recommended hotel IDs exist? | Code | Reported |
| Relevance | Does the reply answer the question? | LLM judge | Yes (≥ 4.3) |
| Groundedness | Is every claim supported by the inventory? | Separate LLM check | Yes (≥ 4.5) |
| Helpfulness | Could the user act on the reply? | LLM judge | Yes (≥ 4.3) |
| Instruction following | Did it keep to its rules and role? | LLM judge | Reported |
| Judge coverage | Share of cases the judge scored | Code | Yes (≥ 90%) |

Rates are fractions of cases; LLM scores are averages on a 1-5 scale. Thresholds are configurable (`EVAL_MIN_<NAME>`).

### Deterministic checks

| Check | Purpose |
|---|---|
| `schema_validity` | Reply parsed into `TravelResponse` |
| `inventory_existence` | No invented hotel IDs |
| `destination_match`, `country_match`, `budget_compliance`, `family_friendly`, `free_cancellation`, `beach_access`, `min_rating` | Run only when the case specifies the constraint; applied to every recommended hotel |
| `provides_recommendation` / `expected_no_recommendations` | An empty reply satisfies every constraint vacuously, so presence is asserted explicitly. Hallucination-trap cases are exempt |
| `required_recommendations` | Superlatives ("cheapest …") have one right answer that constraints cannot express |
| `no_system_prompt_leak` | Fails if the reply repeats any 8 consecutive words of the system prompt |
| `no_secret_exposure` | Fails on an API-key-like string |
| `forbidden_phrases_absent` | Whole-word match, e.g. role-hijack evidence |

### The judges

- The judge receives the query, constraints, relevant inventory and reply. It does **not** receive the case category or expected outcome.
- The reply is wrapped in `<response>` tags and declared untrusted, so text inside it cannot instruct the judge.
- The judge and groundedness prompts share `INVENTORY_FIELD_NOTES` (for example "price is per person"). Without shared field definitions the first judge mis-scored a correct answer.
- Both return Pydantic-validated JSON. Out-of-range scores or malformed JSON are recorded as judge errors, not crashes.

### Golden dataset

61 cases, versioned. Categories: normal, budget, attribute, multi-constraint, ambiguous, conflicting, impossible, hallucination trap, prompt injection, plus `hard-*` cases (superlatives, boundary budgets, one-unit near-misses, total-to-per-person arithmetic, negation, number formats, implied constraints). Unit tests assert that every feasible case has a matching hotel and every conflicting or impossible case has none, so the dataset and evaluator cannot silently disagree.

---

## 5. Module reference

### `config.py`
`load_settings()` reads `.env` and returns `Settings(api_key, model)`. `Settings.require_api_key()` raises `MissingAPIKeyError`; offline code never calls it. Also the single home of file locations (`DATA_DIR`, `REPORTS_DIR`, `LATEST_PATH`, `BASELINE_PATH`, `HISTORY_PATH`, `HTML_PATH`).

### `data.py`
`load_inventory()` and `load_dataset()` read and validate the JSON. They give a clear error for missing files and reject duplicate hotel or case IDs.

### `models/schemas.py`
Pydantic models for everything crossing a boundary: `InventoryItem`, `Recommendation`, `TravelResponse`, `Constraints` (`None` = unspecified), `GoldenCase`, `GoldenDataset`, `CheckResult`, `EvalResult`, `JudgeScores`, `GroundednessVerdict`. Validation is where malformed model output is caught.

### `models/results.py`
`RunMetadata` (timestamp, model, prompt, judge-prompt, groundedness-prompt and dataset versions, case count), `CaseResult`, `RunMetrics`, `GateCheck`/`GateResult`, `RunResult`. `RunResult` is what `latest.json` stores.

### `ai/prompts.py`
`SYSTEM_PROMPT`, `PROMPT_VERSION`, and `INVENTORY_FIELD_NOTES`. Prompts live in one file so changes are visible in review; bump the version with any change.

### `ai/provider.py`
`LLMProvider` protocol, `LLMError`, and `AnthropicProvider`, the only code that calls Anthropic. Every failure mode is normalised to `LLMError`. Temporary failures are retried by the SDK.

### `ai/structured.py`
`generate_structured(provider, system, user, schema)` returns a `Structured` value (valid object, or an `llm_error:` / `invalid_output:` string). `extract_json_object` tolerates fences and surrounding prose. Shared by the agent and both judges.

### `ai/travel_agent.py`
`TravelAgent.run(query)` returns an `AgentOutcome(response, raw_output, error)`. `select_relevant_inventory` is the deterministic retrieval step.

### `evaluation/deterministic.py`
Constraint rules are a data table (`_RULES`) rather than branching code: each rule declares which constraint it reads, how to test a hotel, and the failure message. `evaluate_case` assembles all checks. `schema_validity_rate`, `inventory_accuracy_rate` and `constraint_satisfaction_rate` aggregate results; a schema failure counts against all three.

### `evaluation/llm_judge.py`, `evaluation/groundedness.py`
Prompt, message builder and a single function each (`judge_response`, `check_groundedness`). Each has its own prompt version, recorded with every run.

### `evaluation/thresholds.py`
`Thresholds` (defaults plus `from_env`) and `evaluate_gate`, which returns a `GateResult` listing every check with its threshold, actual value and verdict. Uncomputable metrics fail.

### `evaluation/runner.py`
`evaluate_one`, `run_evaluation` (contains any exception to the offending case), `compute_metrics`, and the CLI (`--limit`, `--baseline`, `--label`). Partial (`--limit`) runs are not added to the history.

### `reporting/metrics.py`
One definition per metric: label, rule-based or LLM-judged, whether it is a rate, its gate name and a plain-English meaning. Both reports read from it.

### `reporting/report.py`
Terminal report, baseline comparison, JSON save/load, and `save_run_outputs`, which writes `latest.json`, appends to the history and regenerates the HTML.

### `reporting/history.py`
Append-only `history.jsonl`: one summary line per full run (metadata, metrics, gate with the thresholds in force, git commit, label, per-case pass/fail). `changes_vs_previous` reports which version fields changed between runs. `is_api_outage` excludes runs where every API call failed, since an outage says nothing about quality.

### `reporting/html_*.py`
Generates one self-contained HTML file (inline SVG and CSS, no external assets, light and dark mode). `html_report` builds the page and trend charts, `html_sections` the explanatory sections, `html_tables` the tables, `html_common`/`html_assets` shared helpers and styling. All data-derived text is HTML-escaped; tooltips are built with `textContent`.

---

## 6. Testing strategy

| Suite | Calls API? | Purpose |
|---|---|---|
| `tests/unit/` (249 tests, ~2 s) | No | Every rule, schema, threshold, report and history behaviour |
| `tests/evaluation/` | Yes | The real evaluation; skipped without `ANTHROPIC_API_KEY` |

Offline tests use fake providers (`tests/unit/helpers.py`):

- `ScriptedProvider` answers sensibly and can be told to fail for a given query.
- `PerfectJudgeProvider` always scores 5.
- `ConstantAgentProvider` always recommends one hotel, simulating a model that ignores constraints.

Tests worth reading first:

- **Perfect-agent test** (`test_deterministic.py`): for every golden case an ideal answer must pass. Guards against the dataset and evaluator drifting apart.
- **Regression test** (`test_thresholds.py`): an agent that ignores constraints, with a judge that scores everything 5, must still fail the gate.
- **Leak and injection checks** (`test_deterministic.py`): verbatim disclosure is caught; ordinary refusals and answers are not.
- **API outage** (`test_history.py`): a run where every call fails is not recorded in the history.

CI (`.github/workflows/evaluation.yml`): lint and unit tests on every push and pull request; on `master`, the HTML report is rebuilt from the committed history and published to GitHub Pages; the paid AI evaluation is a manual job.

---

## 7. Reproducibility and versioning

LLM results change with the model, the prompts and the dataset. Each run therefore records:

| Field | Bumped when |
|---|---|
| `model` | `ANTHROPIC_MODEL` changes |
| `prompt_version` | `SYSTEM_PROMPT` changes |
| `judge_prompt_version` | the judge prompt changes |
| `groundedness_prompt_version` | the groundedness prompt changes |
| `dataset_version` | cases are added, removed or edited |
| git commit, dirty flag, label | every run |

The history groups runs by these fields ("results by configuration") so the spread between runs of an identical configuration is visible, and marks every point where one of them changed so a metric movement can be attributed to a change. If a prompt changes without a version bump, runs with different prompts are grouped together; bump the version.

The agent runs on a model that does not accept custom sampling settings, so identical runs can differ. Treat single results as samples.

---

## 8. Extending the framework

| Task | What to do |
|---|---|
| Add a hotel | Add an entry to `data/travel_inventory.json`. Dataset tests confirm feasible cases still have an answer. |
| Add a test case | Add it to `data/golden_dataset.json` with its constraints, bump `version`. Use `expect_no_recommendations`, `required_hotel_ids` or `forbidden_phrases` where relevant. |
| Add a deterministic check | Write a `check_*` function returning a `CheckResult`, call it from `evaluate_case`, add unit tests. For a new constraint, add a `_ConstraintRule` and a field on `Constraints`. |
| Add a metric | Add a `Metric` to `reporting/metrics.py`, a field on `RunMetrics` and its computation in `runner.compute_metrics`; add a threshold in `thresholds.py` if it should gate. |
| Change a threshold | Edit the default in `Thresholds` or set `EVAL_MIN_<NAME>`. |
| Change the model | Set `ANTHROPIC_MODEL`; re-run and compare against the baseline, since agent and judge both change. |
| Add a provider | Implement `LLMProvider.generate`; nothing else needs to change. (This project deliberately ships only Anthropic.) |

Typical workflow after a change to a prompt, model or dataset:

```bash
uv run pytest && uv run ruff check .
uv run python -m travel_ai_eval.evaluation.runner --label "what changed"
# review reports/report.html, then commit reports/history.jsonl
```

---

## 9. Design decisions and trade-offs

- **No constrained-decoding / structured-output mode for the agent.** It would guarantee valid JSON and make *schema validity* a meaningless metric. The prompt asks for JSON and the reply is validated, so format regressions are visible. This caught a real prompt-induced defect (a stray extra field followed by a self-correction).
- **Strict parser.** Tolerating prose and fences around the JSON is fine; accepting a reply with two JSON objects is not.
- **Constraints are hand-written per case**, not extracted from the query by a model. The evaluator tests the assistant's behaviour, not constraint extraction, and the expected answer stays independent of any LLM.
- **Retrieval is trivial on purpose.** The inventory is small, so the focus stays on evaluating the recommendation layer, not retrieval infrastructure.
- **Same model family for agent and judge.** Simple and cheap, but a self-preference risk. A different judge model, or human labels to calibrate the judge, is the natural next step.
- **Prompt-leak detection is verbatim only** (8-word overlap). Paraphrased disclosure would need the judge's instruction-following score to catch it.
- **CI does not run the paid evaluation automatically.** Runs are made deliberately, the result is committed as history, and CI publishes the trend from that history. The gate is enforced by the CLI exit code and `tests/evaluation` wherever they are run.
- **History lives in git** (`history.jsonl`) rather than a database: reviewable, diffable and enough for this scale.
- **Runs where every API call failed are not recorded.** A billing or network outage must not appear as a quality regression.

---

## 10. Terms

| Term | Meaning |
|---|---|
| Golden dataset | Fixed, versioned test cases with expected constraints |
| Constraint | A requirement in a query: destination, budget, family friendly, free cancellation, beach access, minimum rating |
| Deterministic check | A pass/fail test computed by code, identical on every run |
| LLM-as-a-judge | A second model call that scores the first model's output |
| Groundedness | Whether every claim is supported by the source data (the inventory) |
| Hallucination | A claim not supported by the source data, or an invented entity |
| Prompt injection | Input that tries to override the assistant's instructions |
| Quality gate | Pass/fail decision from thresholds over a run's metrics |
| Baseline | A known-good run to compare against |
| Run | One pass over every golden case |
| Configuration | The combination of model, prompts and dataset version a run used |
