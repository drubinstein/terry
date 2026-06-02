# Experiment plan (pre-registration) — <ONE-LINE TITLE>

> Fill this in **before running anything**. Freezing the metric, N, and decision
> rule up front is what stops metric-shopping and optional-stopping from
> manufacturing the answer you wanted. If you change the design after seeing
> outputs, that's a NEW exploratory experiment — label it and re-confirm on fresh
> cases. See `references/experimental-design.md`.

## Hypothesis

- **Question:** <e.g. "Does opus fix bugs more reliably than sonnet, and is the gap worth the cost?">
- **Prediction:** <what you expect + why — stated before the data>

## Arms (the ONE variable under test)

| Arm | The varying factor (model id OR prompt variant) |
|-----|--------------------------------------------------|
| A   | <e.g. claude-opus-4-8> |
| B   | <e.g. claude-sonnet-4-6> |
| …   | <add arms; but mind the multiple-comparisons trap — pre-register the primary contrast> |

- **Mode:** ☐ completion (API, pinned sampling)  ☐ agent (CLI, pinned tools)  — don't mix.

## Held-constant factors (everything that is NOT the variable)

- Prompt template: <exact text / file — identical across arms except the varying factor>
- Temperature / sampling: <set explicitly, same for all arms>
- System prompt: <explicit, identical>
- Tools / permissions (agent mode): <same allowed-tools set>
- Max output budget: <same>
- Inputs / repo state: <identical; paired by case below>
- Run window: <all arms interleaved in one window — record date/time>

## Test-case suite (paired — every arm sees every case)

- **Source / how chosen:** <sampled to match real usage? hand-picked? — note representativeness>
- **Size:** <n_cases> · **cases file:** `cases.jsonl` (one `{case_id, inputs, [gold]}` per line)

## Response metric + judging

- **Primary metric:** <e.g. unit-tests-pass (objective) | pairwise-preference | rubric score 1–5>
- **Judge:** ☐ objective checker <which> ☐ LLM-as-judge <model + rubric, blinded, position-randomized> ☐ human <rubric, raters>
- **Blinding plan (if subjective):** <neutral labels, shuffled position, label↔arm map kept separate>
- **Secondary metrics (reported, not decisive):** cost_usd, latency_ms, tokens

## Replication & budget

- **N replicates per (arm × case):** <N — N=1 is not an experiment>
- **Total runs:** arms × cases × N = <number> · **est. cost/time:** <budget BEFORE running>

## Decision rule (pre-registered — apply exactly as written)

- **Winner declared only if:** <e.g. "primary metric gap ≥ 10 points AND the 95% CI on the gap excludes 0">
- **Default if no significant difference:** <e.g. "keep the cheaper/faster arm">
- **Tie-breaker on a real-but-small gap:** <e.g. cost, then latency>

## After the run — record (don't edit the plan above)

- Pinned model **version ids** actually used: <…>
- Result table (per arm: metric mean ± 95%, paired effect, cost, latency): <…>
- Verdict (per the decision rule): <winner + gap ± CI | "no significant difference">
- **External-validity caveat:** <holds for THIS suite / judge / date; not universal>
