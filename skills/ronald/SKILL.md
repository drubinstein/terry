---
name: ronald
description: Invoke when comparing models or prompts and you want evidence, not a vibe check — choosing a model for a task (opus vs sonnet vs haiku; Claude vs Codex vs Gemini), A/B testing prompt variants, running a model/prompt bake-off or eval, or confirming a prompt change actually helped rather than got lucky. Runs a controlled A/B/n experiment: one variable, the same test cases through every arm, N replicates for stochastic noise, a blinded judge, a pre-registered metric and decision rule, and an honest "is the gap beyond noise?" — not "B felt better." Starts with a Claude adapter; extensible to Codex/Gemini.
---

# Ronald — controlled A/B experiments across models & prompts

> *"To consult the statistician after an experiment is finished is often merely to
> ask him to conduct a post mortem. He can perhaps say what the experiment died
> of."* — R. A. Fisher

Ronald brings **experimental design** to model and prompt comparison. The default
way people compare models — run the prompt on each once, read the two answers,
pick the one that "feels better" — is an experiment with **N=1, no control, no
blinding, and a metric chosen after seeing the results**. It tells you almost
nothing, because model outputs are *stochastic*: run the same prompt twice and you
get different answers, so a single-sample "A beats B" is often just which sample
you happened to draw.

Ronald replaces the vibe check with a **fair, replicated, blinded, pre-registered
comparison** that ends in an honest verdict — "B wins by X, beyond the noise," or
"no significant difference." It is Fisher's RCT applied to prompts: arms are
treatments, test cases are blocks, replicates absorb sampling noise, the judge is a
measurement instrument you must calibrate and blind.

Six principles, each a guard against a way comparisons lie:

- **One variable.** Change exactly the factor under test — the **model**, *or* the
  **prompt** — and hold everything else constant (same inputs, temperature, system
  prompt, tools, judge). If A and B differ in two things, the result is a confound.
- **Replication.** Outputs are stochastic, so run each (arm × case) **N times**.
  One sample is an anecdote; N gives you the **mean and the spread** — and the
  spread is what tells you whether a gap is real.
- **Pairing (blocking).** Run the **same test cases** through every arm
  (within-subject), so per-case difficulty cancels and you compare like-for-like.
  Paired is far more sensitive than different inputs per arm.
- **Randomize & blind.** Randomize run order, and **blind the judge** to which arm
  produced an output (anonymize labels, randomize A/B position). Otherwise brand
  bias ("it's GPT, must be good") and position bias decide, not quality.
- **Pre-register.** Fix the **metric, the test suite, N, and the decision rule
  before** you look at any output. Choosing the metric after seeing results is how
  every comparison "proves" the answer you already wanted.
- **Compare honestly.** Report each arm's metric **with its spread**, the paired
  effect size, and whether the gap **beats the noise** — plus cost and latency.
  A 1-point edge across 5 noisy runs is nothing.

## When to use

- **choosing a model** for a task — opus vs sonnet vs haiku, or Claude vs Codex vs
  Gemini — before you standardize on one
- **A/B testing prompt variants** — which system prompt / instruction wording / few-
  shot set actually wins
- a **bake-off / eval** across models or prompts you need to defend with numbers
- **confirming a prompt change helped** (vs got a lucky draw)
- quantifying a **quality vs cost vs latency** tradeoff across options

## When NOT to use

- One obvious choice / no real alternative — just pick it.
- You're **iteratively searching** toward a metric (tweak → measure → tweak → …) —
  that's `andrej` (a sequential loop), not a fixed-arm A/B. (Though `andrej` can use
  Ronald to choose among discrete candidates.)
- A throwaway "just try it on both and eyeball it" with no decision riding on it —
  don't over-engineer a one-off. (But the moment a real decision rides on it —
  standardizing the team on a model, shipping a prompt change — it is *not* a
  throwaway: pre-register and replicate.)
- You **can't define a response metric or a judge** — there's nothing to compare
  yet. First make the outcome measurable (a rubric, a checker, a graded score).

## The experiment loop (DESIGN → RUN → JUDGE → ANALYZE → DECIDE)

1. **DESIGN & pre-register.** Write down, *before running*: the hypothesis; the
   **arms** (the one varying factor); the **held-constant factors**; the **fixed
   test-case suite**; the **response metric** + how it's judged; **N** replicates;
   and the **decision rule + threshold**. (Template: `templates/experiment-plan.md`.)
2. **RUN — controlled & randomized.** Execute the matrix **arms × cases × N**
   through ONE harness (identical prompt template, settings, and tools per the
   design), in **randomized order**, capturing every raw output plus cost / latency
   / tokens as artifacts. (Harness: `templates/ab-harness.py`.)
3. **JUDGE — blinded.** Score each output against the metric with the judge **blind
   to the arm**: an **objective checker** where possible (tests pass / exact-match /
   compiles / regex), else **pairwise LLM-as-judge** with randomized position and
   anonymized labels, and/or human grading on a rubric.
4. **ANALYZE.** Aggregate per arm: metric **mean ± spread**; the **paired** per-case
   differences; the **effect size**; and **is the gap beyond the noise** (a CI / a
   simple significance check on N replicates)? Put cost / latency / tokens beside
   quality.
5. **DECIDE & report.** Declare a winner only if the gap clears the pre-registered
   threshold **and** the noise; otherwise **"no significant difference."** Report the
   **full matrix** (not just the winner), the confounds, and the **external-validity**
   caveat: the result holds for *this* suite and *this* time, not universally.

Full detail — Fisher's principles applied to LLMs, the confounds to pin, the
adapters, and the stats — in the references below.

## Mental model: an RCT for prompts

- **Arms = treatments, cases = blocks, replicates = noise control, judge =
  instrument.** A model/prompt comparison is a randomized controlled trial; treat
  it like one.
- **The instrument needs calibration.** An LLM judge has biases (position, length,
  brand, sycophancy). Blind it, randomize position, and validate it against a few
  human labels before trusting it.
- **Stochastic ≠ flaky.** Run-to-run variation is the *signal you're measuring*, not
  a nuisance to suppress — it's why you replicate and why a single run can't decide.
- **The conclusion is about a population.** "Opus beats Sonnet" is shorthand for "on
  *this* task distribution, at *this* time, by *this* judge." Say so.

## Worked example: opus vs sonnet on a bug-fix task

**Hypothesis:** opus has a higher fix rate, but costs more and is slower — is the
quality gap worth it?

1. **DESIGN.** Arms = `{opus, sonnet}` (one variable = model; **same** prompt
   template, temperature, tools, repo state). Suite = **20 fixed** bug-fix tasks,
   **paired** (both models see all 20). Metric = **unit tests pass** (objective,
   automated → no judge bias). **N = 3** replicates per (arm × case) for
   stochasticity → 20 × 2 × 3 = **120 runs**. Pre-registered decision rule: *keep
   the cheaper model unless the costlier one wins fix-rate by ≥ 10 points beyond the
   noise.*
2. **RUN.** The harness runs all 120 in randomized order, pinning temperature, the
   system prompt, and allowed tools identically; it records pass/fail, `cost_usd`,
   and `duration_ms` per run.
3. **JUDGE.** The metric is objective — the test runner is the judge; no blinding
   needed (a key reason to prefer objective metrics when you can).
4. **ANALYZE.** opus **88% ± 4**, sonnet **80% ± 5** (60 runs each). Paired by case:
   opus strictly wins 5/20, sonnet 1/20, tie 14/20. The 8-point gap sits inside ~2σ
   → **not clearly beyond noise** at N=3; opus costs **4×** and is **1.7×** slower.
5. **DECIDE.** Per the pre-registered rule (≥10 pts), **do not adopt** opus — keep
   sonnet — *or* run more replicates to tighten the interval if the decision is
   high-stakes. Report the whole table, not "opus felt smarter."

The discipline is the point: the honest read ("8 ± noise, at 4× cost") is the
opposite of the vibe ("opus is obviously better"), and pre-registration is what
stopped a post-hoc "well opus wrote *nicer* code" from rescuing the conclusion.

## Quick start

1. **Pre-register the design** — fill the plan before running anything:

   ```bash
   cp skills/ronald/templates/experiment-plan.md experiment-plan.md
   # arms (the ONE variable) · held-constant factors · test suite · metric+judge · N · decision rule
   ```

2. **Run the matrix** — same prompt × each arm × N, randomized, capturing outputs +
   cost/latency (starts with a Claude adapter; Codex/Gemini are stubs to fill in):

   ```bash
   cp skills/ronald/templates/ab-harness.py ab-harness.py
   python3 ab-harness.py --arms opus,sonnet --cases cases.jsonl -n 3 --out results.jsonl
   ```

3. **Judge blinded** — objective checker if you have one; else pairwise LLM-judge
   with randomized position + anonymized labels (see `references/judging-and-stats.md`).

4. **Analyze & decide** — per-arm mean ± spread, paired effect, is-it-beyond-noise;
   apply the pre-registered decision rule; report the full matrix + cost/latency +
   the external-validity caveat.

## References

- `references/experimental-design.md` — Fisher's principles applied to LLM
  comparison: one-variable/control, replication (how many runs), randomization,
  pairing/blocking, pre-registration, blinding, the response variable, the
  **confounds you must pin** (model version drift, temperature, system prompt, tool
  availability, context, judge model, time-of-day load), and external validity.
- `references/model-adapters.md` — running the *same* prompt across providers
  uniformly: the adapter interface, the **Claude adapter** (`claude -p` CLI and the
  Anthropic API), the **Codex / Gemini** adapter pattern (confirm flags via
  `--help`), which settings to pin for fairness, capturing cost/latency/tokens, and
  pinning versions against drift.
- `references/judging-and-stats.md` — how to **judge** (objective checkers; LLM-as-
  judge with position-randomization, blinding, a rubric; pairwise vs absolute;
  validating the judge against human labels) and how to **analyze** (per-arm mean ±
  spread, paired differences, effect size, proportion comparison for pass-rates, a
  simple beyond-the-noise check, the many-arms multiple-comparisons trap, and the
  cost/quality Pareto), with a copy-paste aggregation snippet.

## Templates

- `templates/experiment-plan.md` — the **pre-registration** worksheet: hypothesis,
  arms, the one variable, held-constant factors, suite, metric + judge, N, decision
  rule + threshold. Fill it before you run.
- `templates/ab-harness.py` — a runnable matrix runner: adapter interface + a
  working **Claude** adapter (`claude -p --output-format json`, capturing
  result/cost/latency/tokens) + **Codex/Gemini stubs**; runs arms × cases × N in
  randomized order and writes `results.jsonl` for the judge/analysis step.

## Relationship to andrej, jamie & terry

- **`andrej`** is the *sequential* observe→analyze→act loop — change one thing,
  measure, keep-or-revert, repeat — for **iterating toward** a metric. Ronald is the
  *parallel* controlled comparison of **fixed alternatives** (N arms) decided with
  statistics. They share "one variable" and "a scalar metric"; use Ronald to pick
  among discrete candidates, `andrej` to iterate the winner further.
- **`jamie`**'s "quantify reliability `k/N`" is replication in miniature; Ronald
  generalizes it to replication **across arms** with blinding and a decision rule.
- **`terry`** is the natural executor: the matrix (arms × cases × N) is embarrassingly
  parallel, so a fleet can run the arms concurrently in isolated worktrees while
  Ronald defines the *fair experiment* and reads the results.
