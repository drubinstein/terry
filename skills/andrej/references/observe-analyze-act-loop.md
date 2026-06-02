# The Observe→Analyze→Act Loop — in depth

This is the engine of the skill. Every iteration toward a fix, an optimization,
a converged run, or a root cause runs ONE pass of three steps, appends the
result to a ledger, and loops. The discipline is simple to state and hard to
keep: **gather ground-truth signal, interpret it against a model, make exactly
ONE bounded change, measure a scalar, keep-or-revert — never guess.**

It is OODA (Observe–Orient–Decide–Act) with Orient promoted, and it is the
scientific method on a tick budget. The value is not the steps; it is REFUSING
to act on intuition or a sparse log when the live system can tell you the truth.

```
┌──────────────────────────────────────────────────────────────────┐
│  GOAL + a SCALAR METRIC + a FIXED budget  (you cannot loop without │
│                                            all three)              │
│                                                                    │
│  1. OBSERVE   gather ground-truth signal from the LIVE system      │
│               (structured channel > log grep); instrument the      │
│               exact code path if cause unclear; reproduce first    │
│  2. ANALYZE   interpret via a mental model: find hotspot/sink,     │
│   (ORIENT)    oscillation, final state; write 1–2 falsifiable      │
│               hypotheses; don't act on a stale/polluted picture    │
│  3. ACT       ONE variable changed → run to the FIXED budget →     │
│               diff scalar vs baseline → KEEP (commit) or REVERT;   │
│               append the trial to the ledger                       │
│                                                                    │
│  2nd fail on the same wall?  →  ESCALATE (ladder below)            │
│  LOOP                                                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites: goal, scalar metric, fixed budget

Before the first iteration, pin three things. Skipping any one turns the loop
back into guess-and-pray.

- **Goal** — the observable end state that closes the work ("0 flaky failures /
  20 runs", "p99 < 200ms", "pipeline_done flag == True", "val loss < 0.5").
- **Scalar metric** — ONE number that mechanically decides keep-vs-revert. It
  must be cheap to read and monotone toward the goal. A vibe ("seems faster") is
  not a metric.
- **Fixed budget** — a FIXED unit of work per trial (ticks / steps / iterations
  / requests / a fixed-seed N-run sweep). NOT wall-clock — wall-clock makes
  trials incomparable and injects the very nondeterminism you're trying to
  rule out (see "Determinism" below).

---

## Step 1 — OBSERVE

Goal: an accurate, CURRENT picture of the system's behavior — from the system
itself, not from memory, intuition, or a buffered scrollback.

### 1a. Prefer a structured signal channel over log-grep

A buffered log is noisy, unparsed, and lags reality. A structured channel gives
instant, unambiguous facts:

```bash
# Live state from a status endpoint — unbuffered, parseable, exact:
curl -s --max-time 5 http://127.0.0.1:${PORT}/state | python3 -m json.tool

# Machine-readable counters from the run itself (emit them on purpose):
<your-run> --metrics > run.log 2>&1     # visit/bounce/delta/latency counters
```

If you only have a log, make a structured channel FIRST. Adding a `/state`
endpoint or a `--metrics` counter stream pays for itself within two iterations.
(Detail: `metrics-and-hotspot-analysis.md`.)

### 1b. Instrument BEFORE you hypothesize (the #1 rule)

If the root cause is unclear, do NOT fix-and-rerun-and-hope. The FIRST act is to
add observability to the **exact live code path** and read the trace:

```python
# Gate the instrumentation so it doesn't drown the signal, run ONCE, read it:
if i < 30 or i % 50 == 0:
    log(f"iter={i} state={state} input={inp} -> result={ret}")
```

- Log the per-iteration index, the live state, the inputs, and the return value
  of the suspect code path.
- Run it ONCE. READ the trace. The divergence point / the wrong value is almost
  always visible in a single instrumented run.
- Resolve the mechanism from FACT, then write the fix, then REVERT the temporary
  instrumentation.

Why: guessing a one-line fix from sparse logs, re-running, and hoping burns
multiples of the wall-clock vs one instrumented run that shows the mechanism.
The cost of instrumenting is minutes; the cost of guessing is hours of failed
trials. **Measure, don't guess.**

### 1c. Reproduce BEFORE you fix

A fix is unproven until you can reliably reproduce the failure first. Reproducing
proves the bug exists, isolates the conditions, and gives the baseline the
metric will be measured against. If you "can't reproduce it," that is itself the
finding — chase the nondeterminism (it has a cause; see Determinism).

### 1d. Empirical probe over static analysis

For facts about the RUNNING system — reachability, what a flag means right now,
whether a path is actually taken — trust a runtime probe of the live system over
a static model:

- A **runtime probe** (load a checkpoint, take one action, read the resulting
  state) is ground truth.
- A **static model** (a decoded data file, a unioned table, a simulator with
  idealized inputs, a linter's reachability claim) is a HINT. It can be wrong.
- **Static-vs-runtime disagreement is the clue, not a tie to break by
  preference.** When the model says one thing and the live run says another, the
  MODEL is wrong about this case. (Detail + examples in `lessons-and-antipatterns.md` §3.)

---

## Step 2 — ANALYZE (the Orient step teams skip)

OBSERVE gives raw signal; ANALYZE turns it into a decision. This is OODA's
**Orient** — "the linchpin": raw observations interpreted through a mental model,
prior state, and filtered context. A fast loop on a wrong or stale model is worse
than a slower well-oriented one. Don't act on a polluted picture.

### 2a. Find the hotspot / sink / oscillation — mechanically

Have the analyzer surface the facts a human would otherwise eyeball:

- **Hotspot / sink** — the most-visited node, the longest span, the
  highest-failure step. This is where the system is stuck or spending its time.
- **Oscillation / bounce** — the highest back-and-forth A↔B transition. A loop
  that flips between two states is burning iterations without progress.
- **Spike** — WHEN a node got hammered (a per-window delta), not just the total.
  Tells you the phase, not just the aggregate.
- **Final state** — where it ended (the metric, the position, the flags).

Use the `analyze-metrics.py` template: feed it the run, get hotspot + bounces +
final state + top-N. Pick the next action from THAT, not a hunch.

### 2b. Refresh the mental model; write 1–2 falsifiable hypotheses

Build (or refresh) a one-paragraph model of how this subsystem works, then
enumerate hypotheses for the observed hotspot. Constraints from empirical
debugging research:

- **Few hypotheses, not a shotgun.** Good debuggers carry ~2 candidate causes at
  a time and test them one at a time. Forming a CORRECT hypothesis EARLY strongly
  predicts success — so spend the orient effort here.
- **Falsifiable.** Each hypothesis must predict an observable the next experiment
  can confirm or kill ("if it's the shared tmp dir, isolating it drops failures
  to 0"). A hypothesis you can't disprove is useless.
- **Write them down** (in the ledger). Unwritten hypotheses get re-litigated and
  silently widened into shotgun patches.

---

## Step 3 — ACT

Make ONE bounded change, measure, and let the metric decide.

### 3a. ONE variable per experiment

Change EXACTLY ONE thing per run. Bundled changes destroy causal attribution: if
you change three things and the metric moves, you don't know which mattered (or
whether two cancelled). One variable ⇒ any delta has an unambiguous cause. This
is the single most violated rule under time pressure — hold it.

### 3b. Run to the FIXED budget; diff the scalar; keep-or-revert

```bash
<your-run> --max-iters 100000 > trial.log    # ONE change, the FIXED budget
```

- Read the scalar metric from the trial. Compare to baseline.
- **Improved past a real threshold** (beat the baseline by more than noise — a
  falsification gate, not "0.1% better") → **KEEP**: `git commit`.
- **Worse or same** → **REVERT**: `git revert` / `git checkout -- .`. A losing
  change is not "kept for later"; it pollutes the next experiment's baseline.

The git keep-or-revert IS the mechanism — the metric, not your judgment, decides.

### 3c. Prove determinism

A bounded/seeded run is deterministic: same inputs + same budget ⇒ same output.
Confirm a KEEP is real by running it TWICE at the same fixed budget and showing
the outputs are byte-identical:

```bash
# `clean` = pipe through a filter that STRIPS wall-clock/pid/path noise before
# hashing (e.g. `sed 's/<volatile fields>//'`); hash with whatever your platform
# has — shasum (portable), md5sum (Linux), or md5 (macOS):
H1=$(<your-run> --max-iters 100000 | sed 's/<volatile fields>//' | shasum); echo "$H1"
H2=$(<your-run> --max-iters 100000 | sed 's/<volatile fields>//' | shasum); echo "$H2"
# H1 == H2  = deterministic, real result.
# H1 != H2  = a real cause to hunt (NOT "flaky") — see lessons §4.
```

### 3d. VERIFY BEFORE CLAIM

Read the actual end-state artifact that proves the goal — the flag value, the
exit code, the metric readout, the two equal hashes — and record THAT. Never
record success from a celebratory narrative or a misleading log line. No
evidence line = not done.

### 3e. Append the trial to the ledger

Every trial gets one append-only line: the change, the metric before→after,
kept-or-reverted, and which hypothesis it confirmed/killed. The ledger is the lab
notebook — it prevents re-running dead ends and lets anyone reconstruct how you
got here. (Shape: `templates/research_state.json`.)

---

## The escalation ladder (after the 2nd failed attempt on the SAME wall)

Serial iteration on a hard, multi-cause blocker explores one guess per long
cycle — slow and biased toward the first idea. After the SECOND failed attempt
on the SAME wall (don't start a 3rd serial tweak), STOP tweaking and climb:

0. **Re-observe / confirm the wall is real (before spending parallel budget).**
   Run the failure-taxonomy check below: is OBSERVE / ANALYZE / DECIDE / ACT the
   actually-broken phase? Re-observe the CURRENT state and confirm you're not
   stuck on a STALE or INCOMPLETE signal (a flag that's right-but-stale, a
   scorer fed partial inputs — lessons §7), nor acting on a broken PHASE. Climb
   higher only once the wall is confirmed real — otherwise N parallel
   experiments all inherit the same stale-signal bug.
1. **Read the source / spec.** Read the actual implementation or specification of
   the subsystem you're fighting. The mechanism is often stated plainly there;
   you were guessing at documented behavior.
2. **Web-search how others solved it.** Someone has hit this class of problem.
   Search for the pattern, the error, the technique. (Cite what you find.)
3. **Check a reference implementation.** A known-good tool/bot/baseline that
   already does this shows the working approach to copy.
4. **Fan out one experiment per hypothesis.** Save a common checkpoint, then run
   ONE bounded experiment per DISTINCT hypothesis IN PARALLEL (different
   methodologies — e.g. static-sim vs runtime-probe vs visual-render vs
   reference-bot — not parameter tweaks). Each measures the same metric. Merge
   the winner; discard the rest. Failed branches still earn their keep — they
   confirm dead ends.

Why fan out: each serial validation costs a full cycle, so 3 serial tries = 3
cycles of wall time; N parallel experiments from one checkpoint finish in ~1
cycle — far faster exploration. This is the bridge to `terry`, which dispatches
exactly this fan-out as a fleet (one worker per hypothesis, manager merges the
winner). Do NOT fan out genuinely sequential work — only independent hypotheses.

---

## Failure taxonomy: which phase of the loop is broken?

When the loop itself isn't converging, OODA gives the diagnosis — a bad outcome
is a bad phase. Identify WHICH:

| The loop is… | Broken phase | Tell | Fix |
|---|---|---|---|
| Acting on the wrong facts | **OBSERVE** | sparse/buffered logs; never instrumented the live path; can't reproduce | add a structured channel; instrument the exact code path; reproduce first |
| Acting on a wrong/stale model | **ANALYZE/Orient** | hotspot mis-identified; hypotheses keep missing; picture is hours old | refresh the model from the source; re-observe NOW; write falsifiable hypotheses |
| Changes can't be attributed | **DECIDE** | bundled multi-variable changes; no clear metric; "seems better" | one variable per run; pin a scalar metric + fixed budget |
| Runs themselves unreliable | **ACT/execute** | wall-clock budget; "flaky" divergence; claims without evidence | fixed budget; two-identical-run determinism proof; verify-before-claim |

A fast loop on a broken phase just hits the wall faster. Tempo matters relative
to how fast the system changes — but only AFTER the phase is sound.

---

## Loop checklist (copy into your iteration prompt)

- [ ] PRECONDITION: goal + scalar metric + FIXED budget all defined.
- [ ] OBSERVE: signal from a structured channel, not a log grep.
- [ ] OBSERVE: cause unclear? instrument the EXACT live path; run once; READ it.
- [ ] OBSERVE: reproduce the failure (get the baseline) before fixing.
- [ ] OBSERVE: runtime probe > static model for facts about the live system.
- [ ] ANALYZE: find the hotspot/sink + oscillation + final state mechanically.
- [ ] ANALYZE: refresh the mental model; write 1–2 FALSIFIABLE hypotheses down.
- [ ] ACT: change exactly ONE variable.
- [ ] ACT: run to the FIXED budget; diff scalar vs baseline; KEEP or REVERT.
- [ ] ACT: prove determinism (two byte-identical runs); NEVER say "flaky".
- [ ] ACT: VERIFY BEFORE CLAIM — paste the end-state artifact, not a narrative.
- [ ] ACT: append the trial (change → metric → kept? → hypothesis) to the ledger.
- [ ] 2nd fail on the same wall? re-confirm the wall is real (rung 0), then
      climb the escalation ladder; fan out.
