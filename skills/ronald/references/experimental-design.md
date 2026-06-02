# Experimental design for model & prompt comparison

Fisher's three pillars — **control, replication, randomization** — plus pairing,
blinding, and pre-registration, applied to LLM A/B/n testing. The whole point is to
make the difference you report **attributable to the arm**, and **distinguishable
from noise**.

## One variable / control

Change exactly one factor between arms; hold the rest fixed.

- Comparing **models** → same prompt, same temperature, same system prompt, same
  tools, same inputs, same judge; only the model differs.
- Comparing **prompts** → same model + settings; only the prompt text differs.

If you change the model *and* tweak the prompt "to suit it," you've confounded the
comparison — you can no longer tell which factor moved the metric. (This is the same
one-variable rule `andrej` uses for sequential experiments, here applied across
parallel arms.)

**The confounds you must pin** (each silently decides results if left loose):

| Confound | Why it matters | Pin it by |
|----------|----------------|-----------|
| **Model version / drift** | "sonnet" today ≠ "sonnet" next month; silent upgrades move metrics | Pin the **full version id** (`claude-sonnet-4-6`, not `sonnet`); record it; re-run all arms in one window |
| **Temperature / sampling** | higher temp = more variance; different defaults per provider | Set the **same** temperature explicitly for every arm (and report it) |
| **System prompt** | a hidden default system prompt is a second treatment | Set an identical explicit system prompt across arms (`--system-prompt`) |
| **Tool availability** | an arm with more tools is a different agent | Same `--allowed-tools` / same tool set per arm |
| **Context / inputs** | different examples or repo state per arm = unpaired | Identical inputs; pair by case (below) |
| **Judge model / rubric** | the measuring instrument biases the result | One fixed judge + one rubric for all arms; blind it |
| **Time / load** | provider latency and even quality vary by load/time | Interleave arms in one window; don't run A on Monday, B on Friday |

## Replication — how many runs

LLM outputs are **stochastic**: the same (model, prompt) yields different outputs
run to run. So a single output per arm is a *draw*, not a *measurement*. Run each
**(arm × case)** `N` times and treat the per-arm result as a distribution.

- **N = 1** → you're comparing two coin flips; do not conclude anything.
- **N = 3–5** → enough to *see* spread and catch a wildly unstable arm; a rough read.
- **N = 10+** → needed when the expected gap is small or the metric is noisy (e.g.
  a graded score with high variance), or the decision is high-stakes.
- For **pass/fail** metrics, your precision is governed by the proportion: to resolve
  a ~10-point fix-rate gap you need tens of trials per arm, not a handful (a 5/5 vs
  4/5 "win" is noise). See `judging-and-stats.md` for the beyond-noise check.

Set `N` (and total budget = arms × cases × N × per-run cost) in the plan **before**
running, so you don't stop the moment the answer looks the way you hoped.

## Randomization

Randomize anything that could otherwise align with the arm:

- **Run order** — don't run all of A then all of B; interleave/shuffle, so a
  mid-experiment provider slowdown or rate-limit doesn't land entirely on one arm.
- **Judge position** — in pairwise judging, randomize which output is "A" vs "B"
  (LLM judges have a strong position bias). Record the mapping to un-blind later.

## Pairing (blocking)

Run the **same test cases** through every arm (a within-subject / paired design).
Cases vary wildly in difficulty; pairing cancels that per-case difficulty so you
measure the **arm** effect, not the luck of which inputs an arm drew. A paired
analysis (per-case differences) is far more sensitive than comparing two unpaired
group means — you can detect a real effect with far fewer runs.

## Blinding

Bias creeps in through labels. The judge (LLM or human) should **not** know which
arm produced an output:

- anonymize arm names to neutral labels (`output_1`, `output_2`), shuffled per item;
- strip arm-identifying metadata (model name in the text, signature phrasings where
  feasible);
- keep the label↔arm mapping in a separate file, joined back only at analysis.

Unblinded judging measures **brand reputation**, not quality.

## Pre-registration

Write the design down and freeze it **before** looking at outputs: the arms, the
held-constant factors, the test suite, the **metric**, **N**, and the **decision
rule + threshold**. This is the single highest-leverage anti-bias step, because it
forecloses the two most common ways comparisons deceive:

- **Metric-shopping** — running, then picking the metric on which your favorite arm
  wins ("ok it failed more tests but the code is *cleaner*").
- **Optional stopping** — halting the moment the running tally favors the arm you
  like.

If you must change the design after seeing data, that's a **new, exploratory**
experiment — label it so, and confirm it on fresh cases before believing it.

## External validity — what the result does and doesn't say

A result is a claim about **this task distribution, this judge, this time**. Guard
the generalization:

- **Suite representativeness** — 20 hand-picked easy cases don't predict production.
  Sample cases the way real usage is distributed; report suite size and how chosen.
- **Overfitting to the judge** — an arm can win your LLM judge and lose real users;
  validate the judge against human labels.
- **Time-boundedness** — re-run before relying on a months-old result; models drift.
- **Task-boundedness** — "opus > sonnet here" doesn't transfer to a different task;
  don't over-claim.

State these caveats with the verdict. An honest "B wins by 12 ± 4 points on this
50-case suite, at 3× cost, judged by <model>, on <date>" beats "B is better."
