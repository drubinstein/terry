---
name: andrej
description: Invoke when iterating toward a fix/optimization/answer against a live system and tempted to guess from sparse signals — an observe→analyze→act loop over instrumentation + a scalar metric + one-variable bounded experiments + a keep-or-revert gate + an append-only ledger; covers instrument-before-you-hypothesize, the stall escape-hatch, and the guess-and-rerun / stale-context / "flaky" / claim-without-evidence anti-patterns that make iteration spin.
---

# Andrej — the observe→analyze→act iteration loop

Andrej is the **empirical decision-discipline** you run inside every
iteration when you are driving a live system toward a goal — a fix, a perf win,
a converged run, a root cause. Instead of guessing a change from intuition or a
sparse log, you **gather ground-truth signal, interpret it against a mental
model, make exactly ONE bounded change, measure a scalar metric, and keep-or-
revert** — then write down what happened and loop. The data picks the next
action; you never guess.

Like its sibling *terry*, the skill carries a human name: **Andrej** nods to
Andrej Karpathy and the autonomous **edit → run a fixed budget → measure a
scalar → commit-or-revert (via git)** agent loop it generalizes (see
References). This skill is that loop made explicit and domain-agnostic: it
applies to CI triage, performance tuning, flaky-test hunts, hyperparameter
search, incident response, and babysitting any long-running autonomous run.

It is the generalization of five primitives wired into one loop:

- **signal** — ground-truth observation: a trace, a metric stream, a status
  endpoint, a repro, a probe of the live code path (NOT a buffered log grep)
- **scalar metric** — the one number that mechanically decides keep-vs-revert
  (failing-test count, p99 latency, val loss, checkpoint reached)
- **hypothesis** — a written, falsifiable guess at the cause, carried 1–2 at a
  time, not a shotgun of patches
- **bounded experiment** — ONE variable changed, run to a FIXED budget
  (ticks/steps/iterations/time), so any metric delta has an unambiguous cause
- **ledger** — an append-only record of every trial (change → metric → kept?)
  so the loop is forensically reconstructable and never re-litigates dead ends

## When to use

Use Andrej whenever you are about to **change something and re-run to see
if it helped** — i.e. any iterative loop against a system whose behavior you can
observe and measure. Typical shapes:

- a bug/test failure you're tempted to "fix and re-run and hope"
- performance tuning (which change actually moved p99?)
- a flaky / non-deterministic failure you want to make reliable
- hyperparameter / config search toward a metric
- babysitting a long-running autonomous run (an agent, a training job, a
  long-running simulation) — poll its live state each iteration and steer from data
- root-causing an unclear blocker where you don't yet know the mechanism

## When NOT to use

- A single quick, obvious change with an obvious result — just do it; no loop.
- Work with **no observable signal and no measurable outcome** — you can't run
  the loop without a metric to gate on. (First make the system observable, THEN
  loop — see `references/metrics-and-hotspot-analysis.md`.)
- A pure design / planning task with nothing to run yet.
- A genuinely **one-shot, irreversible** action where you can't keep-or-revert.

## The observe→analyze→act loop (3 steps)

Each iteration runs exactly these three steps, then appends to the ledger and
loops:

1. **OBSERVE** — gather ground-truth signal from the LIVE system, not from
   intuition or a stale log. Prefer a structured channel (a status endpoint, a
   machine-readable metric/event stream, a runtime probe) over grepping a
   buffered log. If the root cause is unclear, your first act is to ADD
   instrumentation to the exact live code path and read the trace — instrument
   before you hypothesize. Reproduce the failure before you try to fix it.
2. **ANALYZE** (the orient step teams skip) — interpret the signal through a
   mental model. Find the **hotspot/sink** (the most-visited node, the longest
   span, the highest-failure step), spot **oscillation** (a back-and-forth
   that's burning iterations), read the **final state**, and write down 1–2
   FALSIFIABLE hypotheses for the cause. Don't act on a stale or polluted
   picture — a fast loop on a wrong model is worse than a slower well-oriented
   one.
3. **ACT** — make exactly ONE bounded change targeting the top hypothesis. Run
   it to a FIXED budget. Diff the scalar metric against the baseline: improved →
   KEEP (commit); not → REVERT (git). Then append the trial to the ledger and
   loop. If the same blocker survives the SECOND attempt (don't start a 3rd
   serial tweak), STOP serial iteration and escalate (read the source/spec,
   web-search, or fan out one experiment per hypothesis — the escalation ladder).

Full detail (what to instrument, the orient failure-taxonomy, the
keep-or-revert gate, the stall escape-hatch): **`references/observe-analyze-act-loop.md`**.

## Core disciplines

Six rules, each domain-agnostic and each hard-won. Internalize them; they are
what separate this loop from "tweak and pray."

- **Instrument before you hypothesize.** Unclear blocker? Add observability to
  the exact live code path (per-iteration index / state / inputs / return
  value), run ONCE, READ the trace, resolve the mechanism from fact — THEN
  write the fix. Guessing-then-rerunning is the #1 time sink. *(measure, don't
  guess.)*
- **Empirical probe over static analysis.** For facts about the running system
  (reachability, collision, what a flag means right now), trust a runtime probe
  of the live system over a static model (a decoded data file, a unioned
  table, a simulator with idealized inputs). Static-vs-runtime disagreement is
  itself the clue — the model is wrong, not the system.
- **Structured polling over log-grep.** Expose live state on a structured
  channel (a `/state` endpoint returning JSON; a `--metrics` counter stream)
  and query THAT. Log grep is buffered, unparsed, and noisy; a status endpoint +
  a mechanical analyzer give instant, unambiguous hotspot/oscillation/final-
  state facts so the next action is data-driven.
- **Escalation when stuck.** After the SECOND failed attempt on the SAME wall
  (i.e. don't start a 3rd serial tweak), STOP tweaking. Climb the ladder: read
  the source/spec for the subsystem → web-search how others solved it → save a
  checkpoint and **fan out one experiment per distinct hypothesis**
  (parallel-hypotheses) in parallel, then merge the winner. Serial iteration on
  a hard multi-cause blocker is the wrong shape.
- **Determinism as a tool.** A bounded/seeded system is deterministic: same
  inputs + same budget ⇒ same output. PROVE a fix with TWO byte-identical runs
  (matching output hashes) at a FIXED budget. Run-to-run divergence is NEVER
  "flaky" — it's a real cause (a wall-clock branch, a code change between runs,
  shared mutable state). Hunt it; don't shrug.
- **Verify before claim.** Never report a result (it's fixed / it passes / the
  metric is X) from a celebratory narrative or a misleading log line. Read the
  actual end-state artifact — the flag value, the exit code, the metric readout
  — and paste it. Evidence precedes assertion, always.

## Mental model: the scientific method on a tick budget

Map the loop to disciplined experimental science:

- **Observation = your signal.** Logs, traces, metrics, a reproduced failure —
  the raw data you must explain. No data → instrument first.
- **Hypothesis = a falsifiable cause.** Written down, 1–2 at a time. A good
  debugger carries few hypotheses, not a shotgun.
- **Experiment = ONE variable, FIXED budget.** Change one thing so the result
  has an unambiguous cause; cap the run so trials are comparable and the loop
  can't run away.
- **Measurement = the scalar metric.** The single number that mechanically
  accepts or rejects — not a vibe.
- **Replication = the determinism proof.** Two identical runs = real result;
  divergence = a bug to root-cause, not noise.
- **Lab notebook = the ledger.** Every trial appended: change → metric → kept?
  So you never re-run a dead end and can reconstruct how you got here.

It is also OODA (Observe–Orient–Decide–Act) with **Orient** promoted to a
first-class step: the failure taxonomy in
`references/observe-analyze-act-loop.md` lets you diagnose WHICH phase of a
stalled loop is broken (missing signal? stale model? incoherent change? botched
run?).

## Worked example: one observe→analyze→act cycle (a flaky-test hunt)

A CI job fails intermittently. The instinct is "re-run it." Instead, run one
loop. The ledger before this iteration:

```jsonc
// research_state.json (excerpt)
"goal": "make integration test suite deterministic (0 flaky failures / 20 runs)",
"metric": { "name": "failures_per_20_runs", "direction": "min", "baseline": 6 },
"budget": "20 sequential runs at a FIXED seed",
"hypotheses": [
  { "id": "h-shared-tmpdir", "status": "open",
    "text": "tests share a tmp dir; order-dependent collision" }
],
"trials": []   // append-only; empty so far
```

The iteration:

1. **OBSERVE** — don't re-run and hope. INSTRUMENT first: enable per-test
   timing + the resource each test touches, and run the suite to the FIXED
   budget (20 runs, fixed seed). Capture a structured artifact (a JUnit/JSON
   report), not a scrollback grep. The failure reproduces 6/20 — repro
   confirmed.
2. **ANALYZE** — feed the 20 reports to a mechanical analyzer (the
   `analyze-metrics.py` template generalized): the **hotspot** is one test file
   (5 of 6 failures land there); the **oscillation** is a pass↔fail flip
   correlated with test-execution ORDER. Mental model: a shared mutable
   resource, order-dependent. Top FALSIFIABLE hypothesis: `h-shared-tmpdir`
   (two tests write the same tmp path). Second: a wall-clock branch.
3. **ACT** — change exactly ONE variable: give each test an isolated tmp dir
   (don't also "fix" the clock thing — one variable). Re-run to the SAME budget.
   Metric: 6 → 0 failures/20. Improved → KEEP (`git commit`). PROVE it: two more
   20-run passes produce byte-identical reports → deterministic. VERIFY BEFORE
   CLAIM: paste "0/20, two identical report hashes," not "should be fixed now."
   Append the trial to the ledger; `h-shared-tmpdir` → `confirmed`.

Same shape fits perf tuning (signal = flamegraph; metric = p99; one knob per
run), babysitting a long agent run (signal = `curl /state`; metric = checkpoint
reached; one steer per poll), or hyperparameter search (signal = val-loss curve;
metric = val loss; one hyperparameter per run).

## Quick start

1. **Define the goal, the metric, and the budget** — copy the state template
   and fill the top three keys. Without a scalar metric and a fixed budget you
   cannot run the loop.

   ```bash
   cp skills/andrej/templates/research_state.json research_state.json
   # edit: goal, metric{name,direction,baseline}, budget (a FIXED unit)
   git add research_state.json && git commit -m "andrej: init ledger"
   ```

2. **Make the system observable** — add a structured signal channel before you
   start guessing. A status endpoint and/or a machine-readable metric stream:

   ```bash
   # OBSERVE via a structured channel, not a log grep:
   curl -s http://127.0.0.1:8765/state | python3 -m json.tool   # live state
   <your-run> --metrics > run.log 2>&1                          # emit counters
   ```

3. **Run one cycle and analyze it mechanically** — turn the run's signal into
   root-cause facts (hotspot / oscillation / final state) instead of eyeballing:

   ```bash
   cp skills/andrej/templates/analyze-metrics.py analyze-metrics.py
   python3 analyze-metrics.py run.log     # most-visited node, top bounces, final state
   ```

4. **Make ONE bounded change, gate on the metric, log it.** Change one variable,
   run to the FIXED budget, diff the scalar vs baseline, keep-or-revert, append
   the trial:

   ```bash
   <your-run> --max-iters 100000 > trial.log    # ONE change, FIXED budget
   # metric improved?  → git commit -m "trial N: <change> moved <metric> X→Y"
   # metric worse/same? → git revert / git checkout -- .
   # then append {change, metric, kept} to research_state.json "trials"
   ```

5. **After the 2nd failed attempt on the same wall, escalate** — stop serial
   tweaking (don't start a 3rd); read the source/spec, web-search, or fan out one
   experiment per hypothesis from a common checkpoint and merge the winner (see
   the escalation ladder).

## References

- `references/observe-analyze-act-loop.md` — the 3-step loop in depth: the OODA
  orient/failure-taxonomy, instrument-before-hypothesize, reproduce-before-fix,
  one-variable + fixed-budget + keep-or-revert, the escalation ladder, and a
  copy-paste loop checklist.
- `references/metrics-and-hotspot-analysis.md` — how to make a system
  observable and turn a raw run into root-cause facts: structured polling vs
  log-grep, the metric/signal/budget mapping across domains, hotspot / sink /
  oscillation / spike detection, the empirical-probe-over-static rule.
- `references/lessons-and-antipatterns.md` — the hard-won failure modes of the
  loop itself (guess-and-rerun, tunneling past the stall, static-over-runtime,
  "flaky," claim-without-evidence, stale signal) as Symptom→Root cause→Fix, with
  a quick triage table.

### External sources

- `github.com/yibie/awesome-autoresearch` — a curated index of the
  observe→analyze→act autoresearch methodology and tooling.
- Boyd's **OODA loop** (Observe–Orient–Decide–Act) and the **scientific-method /
  hypothesis-driven debugging** tradition — the general lineage this loop draws on.

## Templates

- `templates/research_state.json` — the append-only research ledger /
  experiment-tracking state file shape, self-documented via `_`-prefixed keys.
- `templates/analyze-metrics.py` — a generic metric/event-stream analyzer
  skeleton: parse a run → hotspot/sink, oscillation/bounce transitions, final
  state, top-N. Adapt the parse patterns to your domain.
- `templates/iteration-prompt.md` — a fill-in-the-blanks contract for running
  ONE disciplined observe→analyze→act iteration (yourself or a dispatched
  worker), with a filled example.

## Relationship to terry

Andrej is the SIBLING of `terry`, not a subset. **Terry** is the
orchestration *manager* — the priority-queue heartbeat that dispatches a fleet
of worker agents across git worktrees and merges their branches. **Andrej**
is the *brain* of the empirical work that happens inside that fleet:

- It is exactly what a terry worker runs in its own context to drive its ONE
  scoped task to a result (observe→analyze→act until the metric gate is met).
- It is also what terry itself runs in the **OBSERVE → INTEGRATE** part of each
  heartbeat tick — poll live state via structured channels, verify the evidence
  line before claiming a merge.
- Terry's `references/lessons-and-antipatterns.md` and this skill's share DNA
  (determinism-not-flaky, verify-before-claim, parallel-hypotheses-when-stuck):
  terry frames them at the fleet level; Andrej frames them at the single-
  iteration level. Use Andrej to decide *what one change to make next*;
  use terry to run *many such loops in parallel and integrate the winners*.
