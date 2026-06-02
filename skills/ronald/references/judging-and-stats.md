# Judging & statistics

Two jobs: turn each raw output into a **score** (judging), then decide whether the
between-arm **difference is real** (analysis). Garbage at either step sinks the
experiment — a biased judge or an eyeballed "A looks higher" both manufacture fake
winners.

## Judging — prefer objective, blind the subjective

### 1. Objective / automated metrics (use these whenever the task allows)

No judge bias, cheap, reproducible. The default choice.

- **Tests pass** (unit/integration) → pass/fail or % passing
- **Exact / fuzzy match** to a gold answer; **compiles / runs / lints**; **schema-
  or type-valid**; **regex / assertion** checks; **task-completed** boolean
- objective side-metrics: **latency, cost, tokens, retries**

If you can express success as a checker, do — then no blinding is needed and the
result is fully reproducible.

### 2. LLM-as-judge (for subjective quality)

When quality is a judgment call (clarity, correctness of prose, code quality):

- **Pairwise > absolute.** Ask the judge "which is better, A or B?" rather than
  "score 1–10." Pairwise is far more stable than absolute scores, which drift.
- **Randomize position, and check both orders.** LLM judges have a strong
  **position bias**. Shuffle which output is shown first; ideally run **both
  orderings** and only count items where the verdict is consistent (flips = a
  coin-flip item).
- **Blind it.** Neutral labels (`output_1/2`), strip model-identifying text.
- **Use a rubric.** Explicit criteria ("correctness, then concision, then style")
  beat "which is better." Ask for a brief justification *then* the verdict.
- **Watch the known biases:** **length** (judges — and human eyeballing — favor
  longer/verbose answers, so "looks more thorough" can be the *worse* answer; control
  for length or instruct against it), **self-preference** (a model favors its own
  family → use a *different* family as judge — **never one that is itself an arm**,
  e.g. don't let GPT judge a contest containing a GPT answer — or use several judges),
  **sycophancy**.
- **Validate the judge.** Have a human grade a **sample** (≥ ~20 items); measure
  judge↔human agreement. If agreement is poor, fix the rubric or switch to human
  grading. An unvalidated judge is an uncalibrated instrument.

**A blinded pairwise judge prompt (copy-paste):**

```
You are scoring two answers to the same task. Be impartial; the labels are
arbitrary and carry no information. Judge on, in order: (1) correctness,
(2) completeness, (3) concision. Do NOT reward length or verbosity for its own sake.

[TASK]
<the case input>

[output_1]
<one arm's answer — position randomized per item>

[output_2]
<the other arm's answer>

Give a 1–2 sentence justification, then end with exactly one line:
VERDICT: output_1   |   VERDICT: output_2   |   VERDICT: tie
```

Run each item in **both** orderings (swap which arm is `output_1`); keep only items
whose verdict is consistent across the swap — a flip is a coin-flip item. Join the
label↔arm map back only at analysis time.

### 3. Human grading

Gold standard for subjective tasks: a rubric, **multiple raters**, and an
inter-rater agreement check. Expensive — so typically used on a sample to
**validate** the LLM judge, which then scales to the full matrix.

## Analysis — is the gap beyond the noise?

You have, per arm, a score for each (case × replicate). Don't compare two single
numbers — account for the spread.

**First, audit the error rows.** A transient API/rate-limit failure scored as 0
silently handicaps whichever arm it hit — drop or re-run `is_error` rows; don't let
them count as quality misses (the harness warns you how many there were per arm).

- **Report mean ± spread, not just the mean.** Per arm: the metric mean and its
  **standard error** (`SE = std / sqrt(n_runs)`). Two arms whose mean ± 2·SE
  intervals overlap are **not** distinguishable at this N.
- **Analyze paired (by case).** Compute the **per-case difference** A−B (averaged
  over replicates), then summarize those differences. Paired analysis cancels
  case-difficulty and is much more sensitive than comparing group means. For
  pass/fail, count cases where A strictly beats B vs B beats A (ties ignored) — a
  **sign test** against 50/50.
- **Pairwise-preference metric** → it's a win rate `w/n`; "beyond noise" iff its
  ~95% interval excludes 50% (binomial). 7/10 wins does **not** exclude 50%; ~70/100
  does.
- **Effect size, not just "significant."** Report the **magnitude** (point gap, or
  Cohen's d for graded scores) and the **cost/latency** beside it. Statistical
  significance with a 1-point quality gain at 4× cost is a practical loss.
- **Many arms → multiple-comparisons trap.** Compare 6 arms and one will look best
  by luck. Pre-register the primary contrast, treat the rest as exploratory, or
  tighten the threshold (Bonferroni-ish).
- **Cost/quality Pareto.** With ≥3 arms, report the **frontier** (quality vs
  cost/latency); the "best" arm is usually a tradeoff pick, not the max-quality one.

### Bootstrap CI on the A−B gap (assumption-light, copy-paste)

Resampling cases gives an honest confidence interval without choosing a named test.
Reads `results.jsonl` rows `{arm, case_id, replicate, score, cost_usd, latency_ms}`
(`score` numeric: 1/0 for pass/fail, or a graded value).

```python
import json, random, statistics as st
from collections import defaultdict

rows = [json.loads(l) for l in open("results.jsonl")]
# mean score per (arm, case), averaging replicates
cell = defaultdict(list)
for r in rows: cell[(r["arm"], r["case_id"])].append(r["score"])
cellmean = {k: st.mean(v) for k, v in cell.items()}
arms = sorted({a for a, _ in cellmean})
cases = sorted({c for _, c in cellmean})

def arm_mean(a, case_subset):
    xs = [cellmean[(a, c)] for c in case_subset if (a, c) in cellmean]
    return st.mean(xs) if xs else float("nan")

for a in arms:                                   # per-arm mean ± SE across cases
    xs = [cellmean[(a, c)] for c in cases if (a, c) in cellmean]
    se = (st.pstdev(xs) / len(xs) ** 0.5) if len(xs) > 1 else 0.0
    print(f"{a:10s} mean={st.mean(xs):.3f}  ±{2*se:.3f} (95%)  n_cases={len(xs)}")

if len(arms) == 2:                               # paired bootstrap on the A-B gap
    A, B = arms
    rng = random.Random(0)                       # fixed seed (Math.random-free)
    gaps = []
    for _ in range(10_000):
        samp = [rng.choice(cases) for _ in cases]   # resample cases w/ replacement
        gaps.append(arm_mean(A, samp) - arm_mean(B, samp))
    gaps.sort()
    lo, hi = gaps[250], gaps[9750]               # 95% CI
    point = arm_mean(A, cases) - arm_mean(B, cases)
    verdict = "REAL (CI excludes 0)" if (lo > 0 or hi < 0) else "NOT beyond noise (CI spans 0)"
    print(f"\n{A} - {B} gap = {point:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  -> {verdict}")
```

If the CI spans 0, you do **not** have a winner at this N — collect more replicates
or accept "no significant difference." Then lay cost/latency next to the gap and
apply the **pre-registered decision rule** — never a post-hoc one.
