# Terry Heartbeat Loop — the Manager Tick

The manager is a long-running loop. It does NOT do the work; it dispatches
workers, integrates what they finish, and keeps the queue moving. Each wake-up
runs exactly ONE tick of five steps, then re-arms and yields. This file is the
deep dive on that tick: what each step does, which tools to use, and the
hard-won handling for stale completions and the resource wall.

```
┌─────────────────────────────────────────────────────────────────┐
│  WAKE (completion notification  OR  fallback timer)               │
│                                                                   │
│  1. OBSERVE     read completions, poll in-flight, drop stale      │
│  2. INTEGRATE   merge each done branch → verify IN MAIN → commit  │
│  3. DEQUEUE +   pick next blocker → dispatch ONE worker in a      │
│     DISPATCH    fresh worktree+branch off current integration HEAD│
│  4. RECORD      update agent_queue.json (done ledger, in_flight,  │
│                 integration_head) → commit the state file         │
│  5. RE-ARM      ScheduleWakeup with a LONG fallback delay         │
│                                                                   │
│  YIELD (do nothing until next wake)                               │
└─────────────────────────────────────────────────────────────────┘
```

## Why completions are the primary wake signal (and the timer is a safety net)

A worker takes minutes-to-hours. If the manager woke on a short fixed timer it
would either (a) burn ticks polling workers that have not moved, or (b) lag a
finished worker by up to the timer interval before merging — both waste wall
time and queue throughput.

So the design is **event-first, timer-backstop**:

- **Completions wake the manager.** When a worker finishes (background Agent
  returns, PushNotification fires, or a completion notification lands), the
  manager wakes *immediately* and integrates that worker while the result is
  fresh and the worktree is still warm. This is the path that actually moves the
  queue forward.
- **The timer only catches what the event path missed.** Re-arm with a LONG
  fallback (e.g. 30–60 min). Its job is to catch: a worker that died without
  emitting a clean completion, an HTTP status endpoint that wedged, a stale
  in-flight entry, or a queue that has free capacity but no pending completion
  to ride in on. If nothing is wrong, a timer wake does a cheap OBSERVE, finds
  no genuine completions, possibly DISPATCHes into spare capacity, and goes back
  to sleep.

Rule of thumb: **if you find yourself relying on the timer to make progress, the
event path is broken — fix it.** A short timer is a smell; it means the manager
is busy-polling instead of being woken by real events.

---

## Step 1 — OBSERVE

Goal: build an accurate picture of (a) which workers genuinely just finished and
(b) the live state of the ones still running. Prefer structured polling over
log-grep.

### 1a. Read completion notifications, then de-dup against the ledger

Completion events are NOT trustworthy on their own — a finished agent re-emits
its final-message echo on later wakes (a **stale completion flush**). Treat any
completion as a *claim* and reconcile it against `agent_queue.json`:

```
for each completion event e:
    if e.agent_id NOT in [w.agent for w in state.in_flight]:
        # already integrated on a prior tick — this is a stale echo
        log "ignoring stale completion flush from {e.agent_id}"
        continue
    genuine_completions.append(e)
```

The invariant that makes this work: an agent is removed from `in_flight` the
moment it is integrated (Step 4). So "is this agent still in `in_flight`?" is the
single source of truth for "is this a new completion?" Re-emitted echoes from an
already-removed agent are no-ops.

### 1b. Poll live state of still-running workers

For each worker still in `in_flight`, poll its status handle — a structured
endpoint, not a log scrape:

```bash
# Each worker owns a unique handle (e.g. --http-port) recorded in in_flight.
curl -s --max-time 5 http://127.0.0.1:${PORT}/state | python3 -m json.tool
```

Use the structured reply (progress markers, current phase, last heartbeat,
free-memory hints) to decide later steps. Only fall back to a log tail if the
endpoint is unreachable. If a poll times out or returns nothing for a worker
that should be live, flag it as a **suspect orphan** (see Step 3 / resource
wall) — do not assume it is fine.

### 1c. One process per handle

Verify exactly one process owns each handle. A finished agent that relaunched a
run can leave an orphan squatting its port; the next worker reusing that handle
collides (two processes, one port).

```bash
# Expect exactly one PID for this worker's port.
lsof -ti tcp:${PORT}
```

If you find an orphan on a handle whose live owner is gone, kill the orphan —
**scoped to the handle, never a broad kill** that would nuke siblings:

```bash
pkill -f "http-port ${PORT}"   # GOOD: scoped to this worker
# pkill -f run_sim.py           # NEVER: kills every sibling run
```

---

## Step 2 — INTEGRATE (manager-only merge + verify-in-main)

For each *genuine* completion from Step 1, merge its branch into the integration
branch. **Only the manager merges.** Workers commit CODE ONLY to their own
branch and never touch the integration branch or another worktree.

### 2a. Merge the worker branch into the integration branch

```bash
git -C "$MAIN" checkout "$INTEGRATION_BRANCH"
git -C "$MAIN" merge --no-ff "$WORKER_BRANCH" -m "merge ${ID}: ${TITLE}"
```

Resolve conflicts deterministically:

- **Two DISTINCT additions at the same spot** (e.g. two new functions, two new
  queue entries) → keep BOTH.
- **Two competing implementations of the SAME fix** → keep the more-complete /
  validated one, drop the duplicate, and record the decision in the ledger.
- **Stale-base regression** — a worker branched off an OLD integration HEAD can
  re-introduce or duplicate already-merged work. Reconcile at merge: drop the
  re-introduced copy, keep the canonical one. (Prevent it up front by always
  branching workers off the *current* HEAD in Step 3.)

### 2b. Verify IN THE MAIN checkout — never the worktree

Worktrees show **spurious failures** from incomplete fixtures (e.g. a partial
`checkpoints/`). Always run the test/verify suite in the main checkout, and trust
ONLY that result:

```bash
cd "$MAIN" && uv run pytest tests/      # expected: full green (e.g. 168 passed)
```

- **Green** → keep the merge; proceed to commit it as part of Step 4 / advance
  `integration_head`.
- **Red** → do NOT keep a broken integration branch. Reset the merge, leave the
  worker branch intact, and re-queue the blocker with the failure noted so the
  next dispatch can fix it:

```bash
git -C "$MAIN" merge --abort   # or: git reset --hard ORIG_HEAD
```

### 2c. VERIFY BEFORE CLAIM

Do not trust a worker's "done" on its word. Read the actual end-state evidence it
reported — the memory value, event flag, byte-identical output hashes, or test
count — before recording success. A completion with no evidence line is an
unverified claim; treat it as not-done and probe before integrating.

---

## Step 3 — DEQUEUE + DISPATCH

Pick the next-priority blocker and dispatch **exactly one** worker for it.

### 3a. Decide whether to dispatch at all (the resource wall)

Before dispatching, decide if there is capacity — machine capacity, and (on a
token budget) spend capacity. **Too many concurrent HEAVY workers OOM/CPU-starve
each other**, and long end-to-end runs then die NON-DETERMINISTICALLY (no
traceback, each run failing progressively earlier). Concurrency policy:

- **Short, bounded fix/iteration runs parallelize fine** — dispatch freely up to
  the machine cap.
- **A LONG end-to-end completion run needs a quiet window.** Pause/serialize the
  heavy slots so it gets the machine; do not start it into the same wall that is
  already killing other runs.
- **Watch the gauges every tick** and gate dispatch on them:

```bash
# macOS: free pages and load average
vm_stat | awk '/Pages free/{print "free_pages",$3}'
uptime  | sed 's/.*load average/load average/'
```

- A slot that is **blocked** (waiting on another worker's fix to land) should be
  **PAUSED, not dispatched** into the wall. Pausing a genuinely-blocked slot is
  not starving it — running it into an OOM is worse.
- **Concurrency is also your token-spend dial.** Every in-flight worker burns
  tokens, so the same cap that protects memory also paces spend: on a budget,
  lower it (down to 1) and let the queue drain serially. The manager wakes on
  completions and otherwise sleeps the long fallback (Step 5), so the loop itself
  costs almost nothing between ticks — the spend is the workers, and the cap sets
  the burn rate.

If there is no capacity (machine OR budget), skip dispatch this tick; the next
completion (which frees a slot) will wake the manager to try again.

### 3b. Pick the next blocker

Sort `queue` by `prio` (and dependency readiness). Skip entries blocked on an
unmerged dependency. Take the top ready one.

### 3c. Create an isolated worktree off the CURRENT integration HEAD

```bash
HEAD_SHA=$(git -C "$MAIN" rev-parse --short "$INTEGRATION_BRANCH")
WT="/path/to/worktrees/${ID}"
git -C "$MAIN" worktree add -f -b "wt-${ID}" "$WT" "$HEAD_SHA"

# Symlink large untracked deps (do NOT copy 100s of MB):
ln -sfn "$MAIN/deps" "$WT/deps"

# Copy any needed checkpoints as UNTRACKED, UNIQUELY-named files so a
# checkout/reset in the worktree never clobbers them:
cp "$MAIN/checkpoints/cp_pre_X.ckpt" "$WT/checkpoints/cp_pre_X_${ID}.ckpt"
```

- Branch off the **current** HEAD, never a stale base (prevents 2b stale-base
  regressions).
- **NEVER `git clean` a worktree** — it deletes the symlinks and the untracked
  checkpoints.
- **One agent per worktree at a time** — two agents in one worktree collide on
  shared files and handles.

### 3d. Dispatch the worker (Agent tool, background)

Dispatch ONE worker with the full dispatch-prompt contract. Use the Agent tool
with `run_in_background` so the manager can yield while it runs; the worker's
completion is what wakes the manager next.

The prompt MUST contain:

- **SCOPE:** exactly one blocker / one hypothesis. Not "fix everything."
- **ISOLATION:** the worktree path `$WT`, branch `wt-${ID}`, unique handle
  `--http-port ${PORT}`, and: *"commit CODE ONLY to this branch; do not touch
  the integration branch or any other worktree."*
- **DRIVE ACTIVELY:** *"do NOT launch a background run and then yield / idle-poll
  — that orphans the process and it dies. Stay in your own context, launch
  bounded segments, read the results, iterate until done."*
- **DETERMINISM BAR:** validate with FIXED/bounded budgets (e.g. `--max-steps`,
  NOT wall-clock) and TWO byte-identical output hashes; never call divergence
  "flaky."
- **HYGIENE:** scope process kills to `--http-port ${PORT}` / the run name; never
  broad kills.
- **REPORT-BACK:** a crisp structured result — what worked (with the evidence
  line), the commit hash(es), how far it got, and the next blocker.

When dispatched, optionally register a lightweight task entry (TaskCreate) so the
in-flight set is visible in the native task list alongside the JSON state.

---

## Step 4 — RECORD (update + commit the JSON state)

`agent_queue.json` is the durable manager state. Update it every tick so the loop
is fully resumable from disk after a crash or restart.

For each integrated worker:

- Remove it from `in_flight`.
- Prepend a dated one-liner to `done_this_session` (the running ledger): what
  merged, the evidence line, the commit sha, and any conflict-resolution
  decision from Step 2a.
- Bump `integration_head` to the new short sha.

For each newly dispatched worker:

- Append an `in_flight` entry: `{id, agent, wt, branch, port, run, started,
  status, title}` (see the template's `_field_docs` for each field) where `title`
  captures *what it is doing + its resume point + the next step*.

Then commit the state file (and the integration-branch advance from Step 2):

```bash
git -C "$MAIN" add tools/agent_queue.json
git -C "$MAIN" commit -m "tick: merged ${MERGED_IDS}; dispatched ${NEW_ID}; head=${HEAD_SHA}"
```

State shape recap:

```json
{
  "_model": "Each tick: observe completions (drop stale echoes), merge done branches + verify in MAIN, dequeue next blocker, dispatch ONE worker in its own worktree, record here, re-arm a long fallback wake.",
  "integration_head": "9cdaaff",
  "in_flight": [
    { "id": "stage7-solve", "agent": "agent_7f3", "wt": "/wt/stage7-solve",
      "branch": "terry/stage7-solve", "port": "8770", "run": "solver-stage7",
      "title": "stage7-solve: at cp_pre_stage7, fixing the transient solve lock; next = reseed retry budget" }
  ],
  "queue": [
    { "prio": 1, "id": "prove-fast-path", "title": "fast-path variant: prove it clears stage 2, blocked on sim" },
    { "prio": 2, "id": "baseline-stage3", "title": "#214 baseline config: stage-3 warmup to threshold 24" }
  ],
  "done_this_session": [
    "2026-06-02 merged stage9-final: PipelineDone=True cost=94 (sha 9cdaaff); kept actual-cost scoring, dropped dup estimated-cost scorer"
  ]
}
```

---

## Step 5 — RE-ARM

Schedule the next heartbeat with a **LONG fallback delay** and then yield. The
timer is the backstop, not the engine — completions wake the manager sooner.

```
ScheduleWakeup(delay="45m", reason="terry heartbeat safety net")
```

Guidance:

- Pick a fallback long enough that it almost never fires before a real completion
  (tens of minutes), but short enough to catch a silently-dead worker within one
  interval.
- Do NOT re-arm a short timer to "make progress" — that means the event path is
  broken; fix the event path instead.
- Only ONE pending fallback at a time. If a completion wakes the manager early,
  the old fallback is superseded by the fresh re-arm at the end of that tick.

---

## Concrete pseudo-transcript of one tick

A completion from the stage9-final worker wakes the manager.

```
WAKE  cause=completion agent=agent_3a1 (stage9-final)

── 1. OBSERVE ──────────────────────────────────────────────
completions: [agent_3a1 (stage9-final), agent_zz9 (stage7-solve)]
reconcile vs in_flight = {agent_3a1, agent_7f3}
  agent_3a1  in in_flight        → GENUINE completion
  agent_zz9  NOT in in_flight    → stale completion flush, IGNORE
poll live workers still in_flight:
  curl http://127.0.0.1:8770/state  (stage7-solve)
    → {phase: "solve", attempt: 4/12, step: 5012, alive: true}   OK, leave running
handles:
  lsof -ti tcp:8769 → 41122 (one pid, the finishing stage9-final run)  OK
evidence check (VERIFY BEFORE CLAIM):
  agent_3a1 report: "PipelineDone=True, cost=94, two runs md5 match: a1b2c3 a1b2c3"
  → evidence present, proceed to integrate

── 2. INTEGRATE ────────────────────────────────────────────
git -C $MAIN checkout integration
git -C $MAIN merge --no-ff wt-stage9-final -m "merge stage9-final: pipeline complete"
  CONFLICT in core/solver/pick_next.py
    two impls of cost scoring: branch=actual-cost(_estimate_cost),
    HEAD=estimated-cost byte → keep actual-cost (validated), drop estimated-cost dup
verify IN MAIN:
  cd $MAIN && uv run pytest tests/  →  168 passed in 13.9s   GREEN
keep merge. new head:
  git -C $MAIN rev-parse --short integration → 9cdaaff

── 3. DEQUEUE + DISPATCH ───────────────────────────────────
resource wall:
  vm_stat → free_pages 540000 (~2.1GB)   uptime → load 3.1 (8 cores)   OK
slot freed by stage9-final → capacity for one short worker
queue top ready: prio=1 prove-fast-path ("prove it clears stage 2")  → SHORT bounded sim, dispatch
worktree off CURRENT head 9cdaaff:
  git -C $MAIN worktree add -f -b wt-prove-fast-path /wt/prove-fast-path 9cdaaff
  ln -sfn $MAIN/deps /wt/prove-fast-path/deps
  cp $MAIN/checkpoints/cp_pre_stage2.ckpt /wt/prove-fast-path/checkpoints/cp_pre_stage2_fast.ckpt
Agent(run_in_background) prompt:
  SCOPE: prove the fast-path variant clears stage 2 at min config, sim-first.
  ISOLATION: wt=/wt/prove-fast-path branch=wt-prove-fast-path --http-port 8771;
             commit CODE ONLY to this branch; touch no other worktree.
  DRIVE ACTIVELY: stay in your context, run bounded sims, iterate; do not yield to a bg run.
  DETERMINISM: fixed --max-steps; two byte-identical hashes; no "flaky".
  HYGIENE: kills scoped to --http-port 8771 only.
  REPORT-BACK: min config + evidence line + commit sha + next blocker.
  → dispatched as agent_b55

── 4. RECORD ───────────────────────────────────────────────
agent_queue.json:
  in_flight: remove stage9-final; add prove-fast-path {agent_b55, /wt/prove-fast-path, 8771}
  done_this_session prepend:
    "2026-06-02 merged stage9-final: PipelineDone=True cost=94 md5 a1b2c3 (sha 9cdaaff);
     kept actual-cost scorer, dropped estimated-cost dup"
  integration_head: 9cdaaff
commit:
  git -C $MAIN add tools/agent_queue.json
  git -C $MAIN commit -m "tick: merged stage9-final; dispatched prove-fast-path; head=9cdaaff"

── 5. RE-ARM ───────────────────────────────────────────────
ScheduleWakeup(delay="45m", reason="terry heartbeat safety net")
YIELD
```

Next wake: whichever fires first — `agent_b55` completing (event path) or the
45-minute backstop. If it is the timer and nothing genuine completed, the tick is
a cheap OBSERVE → maybe DISPATCH into spare capacity → re-arm → yield.

---

## Tick checklist (copy into the manager prompt)

- [ ] OBSERVE: read completions; drop any not in `in_flight` (stale flush).
- [ ] OBSERVE: poll each live worker's status endpoint (not log-grep); flag
      unreachable ones as suspect orphans.
- [ ] OBSERVE: exactly one process per handle; scoped-kill any orphan.
- [ ] INTEGRATE: merge each genuine branch; resolve conflicts deterministically
      (keep-both / keep-validated; drop stale-base dups).
- [ ] INTEGRATE: verify with the suite IN MAIN; abort merge if red.
- [ ] INTEGRATE: VERIFY BEFORE CLAIM — read the evidence line, not the "done".
- [ ] DISPATCH: check the resource wall; pause blocked slots; serialize heavy
      runs.
- [ ] DISPATCH: pick top ready blocker; worktree off CURRENT head; symlink deps;
      copy uniquely-named checkpoints; never `git clean`.
- [ ] DISPATCH: one Agent (background) with the full dispatch-prompt contract +
      unique handle.
- [ ] RECORD: update `in_flight` / `done_this_session` / `integration_head`;
      commit the JSON.
- [ ] RE-ARM: ScheduleWakeup with a LONG fallback; yield.
