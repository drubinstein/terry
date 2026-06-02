# Andrej — Hard-Won Lessons & Anti-Patterns

This is the most valuable file in the skill. Each anti-pattern below has wrecked a
real iteration loop. They are written as: **Symptom → Root cause → Fix**. When a
loop stops converging — same blocker after N tries, "flaky" runs, a fix that
won't stick — scan this list first. The failure is almost always one of these,
not a novel problem.

Read this BEFORE you change-and-rerun, BEFORE you call a divergence "flaky," and
BEFORE you claim anything is fixed.

---

## 1. Guess-and-rerun (the #1 time sink)

**Symptom.** A blocker's cause is unclear, so you guess a one-line fix from the
existing sparse logs, re-run, watch it fail, guess again, re-run again. Five
hypotheses and five long runs later you're no closer, and you've burned hours.

**Root cause.** You acted before you observed. The existing logs don't contain
the fact that explains the failure, so every "fix" is a blind dart. Re-running
without new observability just re-confirms you can't see the mechanism.

**Fix.**
- When the cause is unclear, the FIRST act is to INSTRUMENT the exact live code
  path — log the per-iteration index, state, inputs, and return value of the
  suspect path — run ONCE, and READ the trace.
- The divergence point / wrong value is almost always visible in that single
  instrumented run. Resolve the mechanism from FACT, THEN write the fix.
- One instrumented run costs minutes; five guessed runs cost hours. **Measure,
  don't guess.** Revert the temporary instrumentation once you have the fix.
- If you catch yourself saying "let me try X and see," STOP — you're guessing.
  Go add the log that would tell you whether X is even the right area.

---

## 2. Tunneling past the stall (no escalation)

**Symptom.** The same blocker survives 3, 4, 5 serial attempts. Each attempt is
a full cycle, so you've spent a day on one wall, having explored only one guess
at a time — and you keep reaching for the next variation of the same idea.

**Root cause.** Serial iteration on a hard, multi-cause blocker explores one
hypothesis per long cycle, biased toward the first guess. When several distinct
causes are plausible and none dominates, serial search is the wrong SHAPE — slow
and tunnel-visioned.

**Fix.**
- After the SECOND failure on the SAME wall, STOP serial tweaking and climb the
  escalation ladder (full version in `observe-analyze-act-loop.md`):
  read the source/spec → web-search how others solved it → check a reference
  implementation → **fan out one experiment per distinct hypothesis** from a
  common checkpoint, in parallel.
- Fan-out experiments must be DISTINCT methodologies (static-sim vs runtime-probe
  vs visual-render vs reference-bot), not parameter tweaks of one idea.
- Merge the winner; discard the rest. Failed branches still earn their keep —
  they confirm dead ends so you stop re-trying them.
- This is the hand-off to `terry`: it dispatches the fan-out as a fleet (one
  worker per hypothesis, manager merges the winner). Do NOT fan out genuinely
  sequential work — only independent hypotheses.

---

## 3. Static analysis over runtime ground truth (tooling false-negative)

**Symptom.** A static model — a decoded data file, a unioned/merged table, a
simulator with idealized inputs, a linter's "unreachable", a pathfinder's
"impossible" — says a path/case is dead, so you prune it. But the real system
SUCCEEDS on that exact case when you just run it.

**Root cause.** The static model approximates the world imperfectly. Idealized
inputs, a stale data file, a union that's valid per-context but wrong when merged,
a timing-blind reachability check — any of these makes the model disagree with
the live system. The model is a HINT, not ground truth.

**Fix.**
- For facts about the RUNNING system (reachability, what a flag means now,
  whether a path is taken), trust a RUNTIME PROBE (load a state, take one action,
  read the result) over the static model.
- **Static-vs-runtime disagreement is the clue, not a tie to break by
  preference** — the model is wrong about THIS case. Investigate the model.
- Never prune a critical-path branch on a single static "impossible." If the cost
  of being wrong is high, spend one cheap real run to confirm.
- Staged promotion: screen cheaply with the model, but PROMOTE only what a
  runtime probe confirms. Record probe-vs-reality mismatches so you stop trusting
  that model for that class of question.

---

## 4. Calling deterministic divergence "flaky"

**Symptom.** A run diverges from a prior run, or dies at a different point, and
the reflex is to shrug "flaky" and retry.

**Root cause.** A bounded/seeded system is DETERMINISTIC — identical inputs +
identical budget produce identical output. Divergence is NEVER randomness. It is
one of: a **wall-clock branch** (a code path that depends on `time.time()` / a
`--max-runtime-s` cap that shifts the work done), a **code change** between runs,
a **shared mutable resource** (shared fixtures, a colliding handle/port, a shared
temp dir), or a **resource wall** (OOM/CPU starvation reaping the process).
"Flaky" hides the real cause and guarantees you hit it again.

**Fix.**
- Validate with FIXED/bounded budgets (ticks/steps/iterations/fixed-seed N-run),
  NOT wall-clock. Wall-clock injects the very nondeterminism you're ruling out.
- Prove determinism with TWO byte-identical output hashes across two runs from
  the same base. Two equal hashes = deterministic; differing hashes = a REAL
  cause to hunt.
- When a run "randomly" diverges, check the deterministic causes in order:
  shared state / handle collision → a wall-clock branch → an actual code diff →
  resource exhaustion. ONE of these IS the cause.
- A reproducible failure that fires every run is a GIFT — it proves the bug is
  real and gives a stable baseline. Don't mislabel a consistent failure as flaky
  luck.

---

## 5. Claiming a result without evidence (verify before claim)

**Symptom.** You report "fixed / it passes / the metric improved / done." Later
the end state shows it never happened — the flag was never set, the metric is
unchanged, the output is empty, a celebratory log line lied. Trust evaporates.

**Root cause.** "Done" was asserted from a NARRATIVE or a misleading control-flow
log line ("ALL DONE!"), not from a checked ARTIFACT. Logs fire success messages
from paths that didn't actually achieve the goal; you pattern-matched on the
message.

**Fix.**
- READ THE ACTUAL END STATE before asserting success — the memory value, the
  event flag, the exit code, the metric readout, the two equal determinism
  hashes. Paste it. Evidence precedes assertion, ALWAYS.
- Trust a byte-level / source-level audit over a log line. If you claim "no
  cheats / clean / passing," show the audit output that proves it.
- A result with no evidence line is an unverified claim — treat it as NOT done.
- Re-verify on a second machine/checkout if the stakes are high; a green in one
  context can be a spurious artifact of incomplete fixtures.

---

## 6. Eyeballing a buffered log instead of structured signal

**Symptom.** You're grepping a 50k-line log for status, scrolling for "where is
it now," parsing freeform output with ad-hoc regex, and still guessing at the
hotspot.

**Root cause.** No structured signal channel exists, so the only window into the
system is a buffered, unparsed, noisy log — which lags reality and hides the
ranking facts (hotspot, oscillation, final state) in the noise.

**Fix.**
- Expose live state on a structured endpoint (`curl /state` → JSON) for "where is
  it now," and emit a machine-readable metric/event stream (`--metrics`) for
  "what happened."
- Run a mechanical analyzer over the stream to RANK it into hotspot / bounce /
  spike / final-state facts — pick the next action from those, not from
  scrollback. (See `metrics-and-hotspot-analysis.md`.)
- Adding the channel pays for itself within two iterations. A log grep is a smell
  that the system isn't observable yet.

---

## 7. Trusting a stale-but-suggestive signal (and "the scorer is broken")

**Symptom.** You key a decision off a byte/flag that LOOKS right ("connection
open", "job active") but the system misbehaves anyway. Or you decide a scorer/tool
is broken and start rewriting it — when the real gap is missing input data.

**Root cause.** Two flavors of the same trap: (a) a signal that PERSISTS after the
event it marked — a stale value that reads "true" long after it stopped being
true, so you act on a ghost; (b) assuming a component is buggy when it's actually
being fed incomplete data and silently DEFAULTING (e.g. a lookup table that
covered only part of the input space, defaulting the rest to a wrong constant).

**Fix.**
- Prove LIVENESS, don't trust a static read. If a flag means "menu open," confirm
  the cursor responds to input NOW — don't trust the byte alone (it may be stale).
- Before "fixing" a scorer/tool, check its INPUTS for coverage gaps. Log what it
  actually received and what it returned; a default-to-constant on missing data
  masquerades as a logic bug.
- This is the OBSERVE/ANALYZE failure mode of acting on a polluted picture
  (`observe-analyze-act-loop.md` failure taxonomy) — re-observe the CURRENT state
  and verify the signal is live and complete before you act on it.

---

## 8. Bundled changes / wall-clock budgets (uncomparable trials)

**Symptom.** You changed three things, the metric moved, and you can't say which
mattered (or whether two cancelled). Or two trials aren't comparable because each
ran for "however long it took."

**Root cause.** More than one variable per experiment destroys causal
attribution; a wall-clock budget makes the work-done differ run to run, so the
metric delta conflates your change with timing noise.

**Fix.**
- ONE variable per experiment. If you must change two things, run two trials.
- Cap every trial by a FIXED unit (ticks/steps/iterations/requests), not
  wall-clock, so trials are directly comparable and the loop can't run away.
- Gate keep-or-revert on the scalar metric beating a real threshold (a
  falsification gate), not "looks a bit better."
- Keep an append-only ledger of every trial (change → metric → kept?) so a later
  trial never silently re-bundles a reverted change into its baseline.

---

## Quick triage table

| You observe… | Suspect | Section |
|---|---|---|
| 5 guessed fixes, none worked, never instrumented | Guess-and-rerun | §1 |
| Same wall after the 2nd serial try | No escalation / fan out | §2 |
| Tool says "impossible" but the real run works | Static over runtime | §3 |
| Run "randomly" diverges; urge to retry | Calling it "flaky" | §4 |
| "Done"/"passing" with no artifact to show | Claim without evidence | §5 |
| Grepping a buffered log for status | No structured signal | §6 |
| Acting on a flag that's right-but-stale / "scorer broken" | Stale/incomplete signal | §7 |
| Metric moved but cause unknown; trials incomparable | Bundled change / wall-clock | §8 |
