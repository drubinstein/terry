# Terry — Hard-Won Lessons & Anti-Patterns

This is the most valuable file in the skill. Each anti-pattern below has bitten a
real manager loop. They are written as: **Symptom → Root cause → Fix**. When a
fleet starts misbehaving, scan this list first — the failure is almost always one
of these, not a novel problem.

Read this BEFORE writing a dispatch prompt, BEFORE merging a branch, and BEFORE
believing any worker's "done."

---

## 1. Orphaned runs (the #1 killer)

**Symptom.** A worker reports it "launched the run in the background" and then
yields/returns. Minutes later the run is dead — no traceback, partial progress,
the HTTP status endpoint refuses connections. The process vanished. Re-dispatching
the same worker reproduces it every time.

**Root cause.** The worker armed a background process (or a watcher/heartbeat) and
then ended its own turn / context. Nothing is left driving the process. The
detached child gets reaped, starved, or its session torn down when the agent that
spawned it goes idle. An agent that "fires and forgets" a long run orphans it.

**Fix.**
- Workers MUST drive in their OWN context until the task is done. Do not arm a
  watcher and yield.
- Run work in **bounded segments**: launch a fixed-budget chunk, read its result,
  decide, launch the next chunk — all within the worker's live turn.
- The DISPATCH-PROMPT CONTRACT must include verbatim: *"do NOT launch a background
  run and then yield/idle-poll — that orphans the process and it dies; stay in
  your own context, launch bounded segments, read results, iterate."*
- If a task genuinely must outlive the worker's turn, it belongs to the MANAGER's
  heartbeat (re-armed each wake), not to a worker that's about to return.

---

## 2. Resource wall (concurrency cap / quiet window / pause a blocked slot)

**Symptom.** Several heavy workers run fine alone but, run together, their long
end-to-end completion runs die **non-deterministically** — no traceback, and the
death point creeps *progressively earlier* across attempts. Free memory trends
toward zero; load average pins the core count. Short fix-iteration runs are
unaffected; only the long runs collapse.

**Root cause.** Too many concurrent HEAVY processes OOM/CPU-starve each other. A
long completion run needs a sustained quiet window; when N of them contend, the
kernel reaps whichever crosses the memory line first — and because contention
grows over time, each retry dies sooner. This is NOT flakiness (see #9); it is
resource exhaustion.

**Fix.**
- **Cap concurrency to machine capacity.** Count HEAVY slots against real cores /
  free RAM, not against the size of the queue.
- **Short bounded fix/iteration runs parallelize fine.** A LONG end-to-end
  completion run needs a **quieter window** — pause or serialize the heavy slots
  while it runs, then resume.
- **Watch free memory + load average each heartbeat.** If free RAM is trending
  down or load ≥ cores, do not dispatch another heavy worker; let one drain first.
- **Pause genuinely-blocked slots — don't run them into the same wall.** A slot
  waiting on another worker's fix has no useful work to do; PAUSING it frees
  resources for the run that can progress. Pausing a blocked slot is NOT starving
  it (keep the *priority* slot funded, but a slot that is *blocked on a
  dependency* is correctly paused).
- When in doubt, serialize the single longest/heaviest run and parallelize the
  cheap ones around it.

---

## 3. Handle / port collisions

**Symptom.** A freshly dispatched worker can't bind its `--http-port` (address in
use), or its status endpoint returns another run's state, or two processes both
claim the same port and one silently loses. The "new" worker appears to make no
progress because it's reading/serving a stale process's data.

**Root cause.** A *previous* agent on that handle finished but left an orphan
process still bound to the port (often because it relaunched a run near the end of
its turn — see #1). The next worker reuses the handle and now there are two
processes, one port.

**Fix.**
- Each worker gets a **UNIQUE resource handle** (port/dir/socket). Never recycle a
  handle while its prior owner might still be alive.
- Before dispatching onto a handle, verify **exactly one process owns it**. If an
  orphan is found, kill the orphan and let the live agent own the handle.
- **Scope kills to the handle/port** (`pkill -f "http-port 88NN"` or the
  run/species name). NEVER broad-kill the program name — that nukes siblings (see
  #8 hygiene below and the project's "Agent hygiene" rule).
- Treat "endpoint serves the wrong run's state" as a collision signal, not a bug
  in the new worker.

---

## 4. Stale completion flushes

**Symptom.** The manager "sees" a worker complete, integrates it, dispatches the
next blocker — and then, a heartbeat or two later, sees the *same* worker
"complete" again. Acting on the echo double-merges, re-dispatches, or corrupts the
queue.

**Root cause.** A completed agent re-emits its final-message / transcript tail.
Those echoes look like fresh completion events. The manager has no dedup, so it
reprocesses an already-handled completion.

**Fix.**
- Track handled completions by a stable id (worker id + branch sha). On each
  OBSERVE step, **recognize and no-op** any "completion" whose agent is no longer
  in `in_flight` (it was removed on integration) or whose id is already in
  `done_this_session`.
- Treat the JSON ledger as the source of truth for "what's done," not the most
  recent message echo.
- A completion is only real if it carries NEW evidence (a new commit sha, a new
  end-state line). A bare repeated final message with no new artifact is a flush —
  ignore it.

---

## 5. Tooling false-negatives

**Symptom.** A heuristic probe — pathfinder, simulator, linter, static analyzer —
reports "impossible / unreachable / nonviable," so the manager prunes that branch.
But the real system actually succeeds on that exact case when you just run it.

**Root cause.** The probe models the world imperfectly. Examples: a graph probe
whose timing model mis-registers an edge declares a node "unreachable" that the
live run reaches fine; a cost simulator with worst-case parameters mislabels a
config "nonviable" that succeeds with real parameters; a static config decoder
disagrees with the runtime state table. The probe is a *hint*, not ground truth.

**Fix.**
- **Cross-check any blocking conclusion against ground truth before believing it.**
  Before pruning a path on a probe's "impossible," run the real system (an actual
  bounded run from a checkpoint) on that case.
- Prefer ground-truth probes (runtime state queries) over static/model probes
  for go/no-go decisions.
- Never let a single heuristic kill a critical-path branch. If the probe says
  "no" but the cost of being wrong is high, spend one cheap real-run to confirm.
- Record probe-vs-reality mismatches so the fleet stops trusting that probe for
  that class of question.

---

## 6. Parallel hypotheses when stuck

**Symptom.** The same blocker survives 3+ serial fix attempts. Each serial
iteration costs a long wall-clock run, so three tries burn hours and you're still
stuck, having explored only one guess at a time.

**Root cause.** Serial iteration on a hard, multi-cause blocker explores one
hypothesis per long cycle. When several distinct hypotheses are plausible and none
clearly dominates, serial search is the wrong shape — it's slow and biased toward
the first guess.

**Fix.**
- After a few serial failures on the SAME blocker, STOP iterating serially and
  **dispatch one worker per distinct hypothesis**, in parallel, each in its own
  worktree off current HEAD, each from the same relevant checkpoint.
- This is **intentional redundancy on the critical path** — accept the wasted work
  on the losing branches as the price of 5× faster exploration.
- Each hypothesis worker tests EXACTLY ONE idea and reports a crisp
  worked/didn't-work + evidence.
- **Merge the winner; discard the rest.** Record which hypothesis won and why in
  the ledger so the fleet doesn't re-litigate it.
- Also use this shape proactively when entering a NEW design space with multiple
  plausible strategies and no clear front-runner — don't wait to get stuck.

---

## 7. Verify before claim

**Symptom.** A worker says "done — the job finished / migration complete / tests
pass." The manager merges it. Later the end state shows it never actually
happened: the flag was never set, the counter is wrong, the output is empty.
Trust was misplaced.

**Root cause.** "Done" was asserted from a worker's narrative, not from a checked
artifact. Agents (and managers) pattern-match success without reading the actual
end state.

**Fix.**
- **Read the actual end state before asserting success** — the memory address, the
  event flag, the output file, the test exit code. Evidence precedes assertion,
  always.
- A worker's REPORT-BACK must carry the **evidence line** (the flag value, the
  commit sha, the final-state readout). No evidence line → treat as not-done.
- The manager re-verifies on integration: merge, then run the **verify/test suite
  in the MAIN checkout** (not the worktree — see #8) and confirm the claimed
  end-state artifact with your own eyes before committing.
- Never let a worker's "done" alone advance the queue. Promote to
  `done_this_session` only after you've seen the artifact.

---

## 8. Stale-base regression (+ verify-in-main, scoped-kills hygiene)

**Symptom.** A merged worker re-introduces a bug that was already fixed, or adds a
second copy of code that already exists on the integration branch, or "rewrites"
working code into a regression. The worktree's own test run looked green; the main
checkout fails (or vice versa).

**Root cause.** The worker branched off a **stale integration HEAD**. It never saw
the already-merged fix, so it re-implements (and possibly breaks) it, or
duplicates it. Compounding this: worktrees show **spurious test results** because
their fixtures/checkpoints are incomplete — so a worktree's green is not
trustworthy.

**Fix.**
- **Always branch off CURRENT integration HEAD**, not stale `main`/old base:
  `git worktree add -f -b <branch> <WT> <integration-HEAD>`.
- At merge time, **reconcile against current HEAD**: for two distinct additions at
  the same spot keep BOTH; for two competing implementations of the same fix keep
  the more-complete/validated one and drop the duplicate; verify the worker's
  "before" matches current code before trusting its "after."
- **Verify with the test suite in the MAIN checkout, never the worktree.** Never
  trust a worktree's test count (incomplete fixtures → spurious pass/fail).
- **NEVER `git clean` a worktree** — it deletes the symlinked deps and the
  untracked, uniquely-named checkpoints. Keep checkpoints untracked + unique so a
  checkout/reset never clobbers them.
- **Scope process kills to the worker's own handle/port/run name**, never a broad
  kill of the program name — broad kills nuke sibling runs. (Hygiene rule that
  prevents one worker's cleanup from killing the fleet.)

---

## 9. Determinism, not "flaky"

**Symptom.** A run diverges from a prior run, or dies at a different point, and the
instinct is to shrug it off as "flaky" and retry.

**Root cause.** A step-bounded system is **deterministic**. Identical
inputs produce identical outputs. Divergence is NEVER randomness — it is one of:
a wall-clock branch (timing-dependent code path), a code change between runs, a
shared mutable resource (shared fixtures, a colliding handle), or the resource
wall (#2) reaping the process. Calling it "flaky" hides a real cause and
guarantees you'll hit it again.

**Fix.**
- **Validate with FIXED/bounded budgets, not wall-clock** (e.g. `--max-steps`, not
  `--max-runtime-s`). Wall-clock budgets introduce the very nondeterminism you're
  trying to rule out.
- Prove determinism with **two byte-identical output hashes** (MD5 of the cleaned
  log) across two runs from the same base. Two identical hashes = deterministic;
  differing hashes = a real cause to hunt, not flakiness.
- When a run "randomly" dies, check the deterministic causes in order: shared
  state / handle collision (#3), stale base (#8), resource wall (#2), a wall-clock
  branch, an actual code diff. One of these IS the cause.
- Note: a "seeded" / preloaded / fixture-primed run ≠ an excuse for
  nondeterminism. A run started from injected state is still deterministic; treat
  its divergences the same way.

---

## Quick triage table

| You observe… | Suspect | Section |
|---|---|---|
| Background run dies after worker yields | Orphaned run | §1 |
| Long runs die earlier each retry, RAM low | Resource wall | §2 |
| Port in use / endpoint serves wrong state | Handle/port collision | §3 |
| Same worker "completes" twice | Stale completion flush | §4 |
| Probe says "impossible" but real run works | Tooling false-negative | §5 |
| Same blocker after 3+ serial tries | Need parallel hypotheses | §6 |
| "Done" with no artifact to show | Verify before claim | §7 |
| Merge re-breaks a fixed bug / dup code | Stale-base regression | §8 |
| Run "randomly" diverges; urge to retry | Determinism, not flaky | §9 |
