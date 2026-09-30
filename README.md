# Travel AI Evaluation Lab

A small, readable framework for evaluating a **non-deterministic AI recommendation layer**, modelled on the kind of assistant a travel-commerce platform might put in front of its inventory.

It is **not** a booking app. The travel agent is deliberately simple; the interesting part is how its output is tested, scored and gated before a change can ship.

> **Everything here is synthetic.** The 20 hotels in `data/travel_inventory.json` are fictional and were written for testing. No real customer data, prices or availability are used anywhere.

This is a learning/portfolio project. It is **not production-ready** (see [Limitations](#limitations)).

---

## Why it exists

LLM output changes between runs, models and prompts, so a normal `assert response == expected` test does not work. This project shows a practical answer:

- assert the things that are *facts* deterministically,
- use an LLM judge only for the things that are genuinely *subjective*,
- run both over a versioned golden dataset,
- turn the results into metrics and compare them with thresholds,
- fail the build when quality drops.

```
Deterministic checks
        +
LLM-as-a-judge
        +
Golden dataset
        +
Quality thresholds
        =
AI release gate
```

## Architecture

```
                   data/golden_dataset.json          data/travel_inventory.json
                      (versioned cases)                 (synthetic source of truth)
                              │                                   │
                              ▼                                   ▼
                        ┌───────────────────────────────────────────────┐
                        │ Runner (evaluation/runner.py)                 │
                        └───────────────────────────────────────────────┘
                              │ for each case
                              ▼
                     Travel agent (ai/travel_agent.py)
        select inventory by destination → Anthropic → JSON → Pydantic validation
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
   Deterministic evaluation            LLM evaluation (Anthropic)
   (no LLM, hard constraints)          - llm_judge.py: 5 rubric scores, 1-5
   - schema validity                   - groundedness.py: unsupported claims
   - inventory existence
   - destination/budget/family/
     cancellation/beach/rating
   - presence / no-recommendation
   - prompt-leak, secrets, role hijack
              │                                │
              └───────────────┬────────────────┘
                              ▼
                      Aggregated metrics
                              │
                              ▼
                 Quality thresholds (thresholds.py)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
                  PASS                 FAIL
              exit code 0           exit code 1
                              │
                              ▼
        Terminal report + reports/latest.json (+ baseline comparison)
```

Anthropic is the only LLM provider. `ai/provider.py` defines an `LLMProvider` protocol with a single `AnthropicProvider` implementation, so application logic is not coupled to the SDK.

## Quick start

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env        # then set ANTHROPIC_API_KEY (and optionally ANTHROPIC_MODEL)

uv run pytest                        # offline unit tests only, zero API calls
uv run pytest tests/evaluation -s    # full AI evaluation (real API calls, see Cost)
uv run python -m travel_ai_eval.evaluation.runner            # same run via the CLI
uv run python -m travel_ai_eval.evaluation.runner --limit 5  # cheap smoke run
```

- Plain `pytest` never calls Anthropic, even if a key is present. The paid suite must be requested explicitly.
- `tests/evaluation` skips with a clear message when `ANTHROPIC_API_KEY` is not set.
- The CLI exits `0` on PASS, `1` when the quality gate fails, `2` when the API key is missing.

### Configuration

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for evaluation. Read from the environment / `.env`. Never hard-coded. |
| `ANTHROPIC_MODEL` | Model used for the agent **and** the judge. Default is set in `config.py`. |
| `EVAL_MIN_<METRIC>` | Override a threshold, e.g. `EVAL_MIN_HELPFULNESS=4.0`. Metrics: `SCHEMA_VALIDITY`, `CONSTRAINT_SATISFACTION`, `RELEVANCE`, `GROUNDEDNESS`, `HELPFULNESS`, `JUDGE_COVERAGE`. Rates are fractions (`0.95` = 95%). |

## Evaluation strategy

### Deterministic checks come first

Price, destination, inventory membership and boolean amenities are facts in the inventory. Comparing them is exact, free, repeatable and explainable, so **no LLM is involved** (`evaluation/deterministic.py`). Every case gets structured, actionable results:

```json
{
  "passed": false,
  "checks": [
    { "name": "budget_compliance", "passed": false,
      "reason": "Recommended hotel DXB003 costs £2400 but maximum budget is £1500." }
  ]
}
```

Checks include: schema validity, inventory existence (no invented hotel IDs), destination / country, budget, family-friendly, free cancellation, beach access, minimum rating, and adversarial checks (system-prompt leakage, secret-like strings, forbidden phrases such as pirate slang after a role-hijack attempt).

Two checks guard against gaming. An empty answer satisfies every constraint vacuously, so cases that should produce a recommendation must produce at least one, and cases that should not (impossible requests, unknown hotels, pure injection attempts) must produce none.

**`constraint_satisfaction_rate`** = cases where *every* deterministic check passed ÷ total cases (e.g. 47 / 49 = 95.9%).

### LLM-as-a-judge covers what rules cannot

Whether an answer is relevant, helpful, honest about unknowns and stays in role is subjective. Two Anthropic calls per case cover this:

- `llm_judge.py` scores **relevance, groundedness, helpfulness, constraint satisfaction, instruction following** from 1 to 5, validated with Pydantic.
- `groundedness.py` lists **unsupported claims** (e.g. "has a Michelin-starred restaurant" when the inventory says nothing about restaurants). Its score is what the groundedness gate uses.

The judge receives the query, constraints, relevant inventory and response. It never receives the case category or the expected outcome. The response is wrapped as untrusted data so it cannot instruct the judge.

### Deterministic failures cannot be overridden

Nothing an LLM says can turn a deterministic failure into a pass:

- `EvalResult.passed` is true only if every deterministic check passes.
- The quality gate requires **every** threshold to be met; a high judge score cannot compensate for a low constraint-satisfaction rate. `tests/unit/test_thresholds.py` proves this with a simulated agent that ignores all constraints while a fake judge gives perfect scores: the gate fails.

### Why an LLM judge alone is not enough

Judges are useful but imperfect:

- They are non-deterministic and their scores drift across model and prompt versions.
- They can be lenient or harsh in ways that are hard to see. An over-budget hotel scored 4/5 on groundedness because its facts were true; only the deterministic budget check catches it.
- Judge scores are compressed (most answers get a 4 or 5), so they are poor at detecting small regressions.
- This project judges with the same model family that generates the answers, which risks self-preference bias.
- Judges can be fooled by the text they evaluate, so it is treated as untrusted input, but that is mitigation, not a guarantee.

Hence multiple mechanisms: exact checks for facts, a dedicated groundedness check for invention, a rubric judge for tone and usefulness, and thresholds over a fixed dataset.

## Golden dataset

`data/golden_dataset.json` holds **49 cases** (currently version `1.1.0`). Each has a query, language, category and expected constraints. It is intentionally not all happy paths:

| Category | What it tests |
|---|---|
| normal, budget, attribute | Ordinary requests, £ limits, cancellation / family / beach / rating |
| multi_constraint | Several constraints at once (the highest-value cases) |
| ambiguous | "Somewhere warm in December": help without inventing requirements |
| conflicting | Contradictory constraints; no fabricated answer |
| impossible | "A hotel on Mars" |
| hallucination_trap | Hotels/facts not in the inventory ("Atlantis Moon Resort") |
| prompt_injection | Reveal-your-prompt, role hijack, secret extraction, budget override, fake "system update" (some in Spanish) |

Non-English queries are included. Every feasible case is checked by unit tests to have at least one matching hotel in the inventory, and every conflicting/impossible case to have none, so the dataset and evaluator cannot silently disagree.

A dataset is a snapshot of expected behaviour. Change the cases → bump `version`, because scores are only comparable between runs on the same version.

`price_gbp` is defined as the **price per person**. Budget constraints are compared against it directly.

## Run metadata and reproducibility

Every run records:

```json
{ "timestamp": "...", "model": "...", "dataset_version": "...",
  "prompt_version": "...", "judge_prompt_version": "...", "total_cases": 49 }
```

Traditional tests are reproducible: same code, same input, same result. LLM systems are not. The same prompt can produce different text on two runs, and results move when the **model version**, the **prompt** or the **dataset** changes. The recorded metadata is what makes two reports comparable. Compare like with like, and treat a change in any of those fields as a reason results may differ.

Notes:
- Changing `ANTHROPIC_MODEL` changes agent *and* judge behaviour and can move every metric. Re-baseline after switching.
- Bump `PROMPT_VERSION` (`ai/prompts.py`) and `JUDGE_PROMPT_VERSION` (`evaluation/llm_judge.py`) when their prompts change.
- The default model does not accept custom sampling settings, so runs can differ from one another. A single borderline case can flip. Look at trends and thresholds, not a single number.

## Quality gate

Defaults (`evaluation/thresholds.py`, all configurable):

| Gate | Threshold |
|---|---|
| Schema validity | 100% |
| Constraint satisfaction | ≥ 95% |
| Relevance | ≥ 4.3 / 5 |
| Groundedness | ≥ 4.5 / 5 |
| Helpfulness | ≥ 4.3 / 5 |
| Judge coverage | ≥ 90% of cases scored |

Judge coverage exists so that failed judge calls cannot silently shrink the sample the averages are computed on. A metric that cannot be computed fails the gate.

Example terminal report (from a real run; yours will differ):

```
========================================
Travel AI Evaluation
========================================

Dataset: 49 cases (version 1.1.0)
Model: claude-sonnet-5-5
Prompt version: 1.1.0 (judge 1.1.0)

Deterministic Evaluation
----------------------------------------
Schema validity:                100.0%
Constraint satisfaction:        100.0%
Inventory accuracy:             100.0%

LLM Evaluation
----------------------------------------
Relevance:                    4.90 / 5
Groundedness:                 5.00 / 5
Helpfulness:                  4.57 / 5
Instruction following:        4.98 / 5

Quality Gates
----------------------------------------
Schema validity >= 100%         PASS
Constraints >= 95%              PASS
...
========================================
QUALITY GATE: PASS
========================================
```

When something fails, a **Failures** section lists the case, the check and the reason.

## Regression testing

A run is written to `reports/latest.json`. To compare future runs against a known-good one:

```bash
cp reports/latest.json reports/baseline.json    # commit this if you want CI to compare
uv run python -m travel_ai_eval.evaluation.runner --baseline reports/baseline.json
```

The report then adds a comparison table with regression arrows and warns if the model, prompt version or dataset version differ:

```
                              Baseline   Current
Constraint satisfaction         97.6%     91.0%  ↓
Groundedness                     4.95      4.20  ↓
```

The comparison is informational: the gate decides PASS/FAIL from absolute thresholds. No database is used, only JSON files. Only `reports/baseline.json` is un-ignored by `.gitignore`; `latest.json` is generated output.

**To try a deliberate regression:** edit `SYSTEM_PROMPT` in `ai/prompts.py` to tell the assistant to ignore the budget, run the evaluation, and watch constraint satisfaction drop and the gate fail. The same behaviour is exercised offline (with a fake agent) by `test_regression_ignoring_constraints_fails_the_gate_despite_perfect_judge`.

## Continuous integration

`.github/workflows/evaluation.yml` has two clearly separated jobs:

1. **Unit tests**: offline, no secrets, no API calls, runs on every push and PR.
2. **AI evaluation**: runs only after unit tests pass and only when `secrets.ANTHROPIC_API_KEY` exists (fork PRs get a skip notice instead). It runs `pytest tests/evaluation`, **fails the build if the quality gate fails**, and uploads `reports/latest.json` as an artifact. An optional repository variable `ANTHROPIC_MODEL` selects the model.

Treating the evaluation as a release gate: a prompt or model change that lowers quality below the thresholds blocks the merge, the same way a failing test would.

## Cost control

- Unit and deterministic tests make **zero** API calls.
- The evaluation makes at most **3 calls per case** (agent, judge, groundedness), so about 150 calls for 49 cases, and none for the judge steps when the agent's reply is invalid. There are no duplicate judge calls.
- Cases run sequentially (a full run takes roughly 6–8 minutes). Concurrency is a possible later optimisation, deliberately not added yet.
- Use `--limit N` for cheap smoke runs. Small samples make the gate noisy, so use full runs for decisions.

## Error handling

API failures, rate limits (the SDK retries with backoff), timeouts, refusals, truncated output, invalid JSON, schema failures, missing inventory and missing API key are all handled. A bad model reply is **recorded as a failed case, not raised**; unexpected exceptions are contained per case, so one failure never aborts the run.

## Project layout

```
data/                  golden_dataset.json, travel_inventory.json
src/travel_ai_eval/
  config.py            settings (.env, ANTHROPIC_MODEL)
  data.py              dataset / inventory loading + validation
  ai/                  provider.py, prompts.py, travel_agent.py, structured.py
  evaluation/          deterministic.py, llm_judge.py, groundedness.py,
                       thresholds.py, runner.py
  models/              schemas.py, results.py
  reporting/           report.py
tests/unit/            offline tests
tests/evaluation/      paid AI evaluation (skips without a key)
reports/               latest.json (generated, git-ignored), baseline.json
```

## Limitations

Please read these before drawing conclusions.

- **Synthetic, tiny inventory** (20 hotels). Real catalogues have far more variety, noise, stale data and edge cases.
- **Small dataset** (49 cases). Rates move in steps of about 2 points per case; the gate is noisy and can flip on one borderline result. Averages of 1–5 judge scores hide variance.
- **The LLM judge is imperfect**: non-deterministic, compressed scores, possible self-preference bias (same model family as the agent), and it was tuned against a handful of examples. Judge prompt changes shift scores.
- **Prompt-leak detection only catches verbatim disclosure** (8-word overlap). A paraphrased leak would slip past the deterministic check.
- **Passing adversarial cases is not proof of safety.** It shows this model resisted these particular attacks.
- **Prompt and thresholds were tuned against this dataset**, which is a form of overfitting. The helpfulness threshold was met after adding an explicit "next step" instruction to the agent prompt; a fresh held-out set would be needed to say anything stronger.
- **Retrieval is trivial**: destination/country name matching, then the whole inventory. It is not representative of real retrieval.
- **No production traffic**, no real booking or availability API, no latency/cost SLOs, no human evaluation loop, and no calibration of the judge against human labels.
- Constraints for each case are hand-written, not extracted from the query by a model, so the evaluator does not test constraint extraction itself.

Sensible next steps: a held-out dataset, human-labelled judge calibration, a second judge model, repeated runs to measure variance, and richer retrieval.
