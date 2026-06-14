---
name: terry
description: Invoke when orchestrating a FLEET of parallel long-running agent tasks via a priority-queue manager over git worktrees, OR when you want a producer-consumer task queue for agents that caps concurrency to avoid OOM and pace token spend on a budget — agent queue + task list + dispatched agents + a self-pacing heartbeat loop. Covers capacity-gated dispatch (backpressure), worktree isolation, the manager-only merge protocol, and the resource/orphan/determinism anti-patterns that make fleets fail.
---

# Terry — agent-fleet orchestration

Terry is a long-running **manager loop** that drives a fleet of independent
worker agents. Each worker does ONE well-scoped, long-running task in its OWN
git worktree + branch. They coordinate through a single JSON priority-queue
state file, and **Terry is the only one that merges** worker branches into an
integration branch — distributed-VCS style.

It is the generalization of four primitives wired into one durable loop:

- **agent queue** — a JSON state file (`agent_queue.json`)
- **task list** — native `TaskCreate` / `TaskList`
- **dispatched agents** — the native Agent tool (`run_in_background`)
- **heartbeat** — `ScheduleWakeup` (or a `/loop`) that self-paces the manager

Terry is **two tools in one**:

- a **parallel fleet** — N workers run concurrently, each merged as it finishes
  (distributed-VCS style); and
- a **producer-consumer queue with backpressure** — the manager dispatches ONLY
  into free capacity, so concurrency stays capped. That cap is your throttle:
  keep peak memory under what the machine holds (**no OOM**), and **pace token
  spend when you're on a budget** — lower the cap (down to 1) for a strictly
  serial queue that drains the backlog one task at a time. Because the manager
  wakes on completions and otherwise sleeps a long fallback, the loop itself
  idles cheaply between ticks; the spend is the workers, and the cap controls the
  burn rate.

## When to use

Use Terry when you have **N independent long-running tasks** that each take
many minutes-to-hours, benefit from running concurrently, and are merged as
they finish. Typical shapes:

- parallel exploration of competing hypotheses (one worker per hypothesis)
- a fleet of per-target migrations (one worker per target)
- multiple validation / iteration runs against a shared codebase
- a **backlog you want drained at a controlled rate** — cap concurrency (even to
  1) to stay under memory and to pace token spend on a budget
- anything where **dispatch → it runs a while → it reports → merge → dispatch
  the next blocker** repeats.

## When NOT to use

- A single quick task — just do it.
- Work that must be strictly sequential because each step needs the previous
  step's result — no parallelism to exploit. (Terry's queue still works as a
  paced one-at-a-time consumer, but you don't need the fleet machinery.)
- A single job so large that even ONE worker won't fit the machine — Terry paces
  *concurrency*, but can't shrink a worker below its own footprint (see the
  resource-wall lesson in `references/lessons-and-antipatterns.md`).

## The heartbeat loop (5 steps)

Terry wakes on a completion notification or a fallback timer and runs:

1. **OBSERVE** — read completion notifications; poll live state of in-flight
   workers (HTTP status endpoint or log tail, preferring structured polling).
   Recognize and IGNORE stale completion echoes from already-handled agents.
2. **INTEGRATE** — for each genuinely-completed worker, merge its branch into
   the integration branch, resolve conflicts deterministically, and run the
   test/verify suite **in the main checkout** (never the worktree). Commit only
   if green.
3. **DEQUEUE + DISPATCH** — pick the next-priority blocker from the queue;
   dispatch exactly ONE worker in a fresh worktree+branch off the **current**
   integration HEAD, with a unique resource handle (port/dir).
4. **RECORD** — update the JSON state file (completed → `done_this_session`
   ledger; add the new `in_flight` entry; bump `integration_head`); commit it.
5. **RE-ARM** — schedule the next heartbeat with a LONG fallback delay.
   Completions wake Terry sooner; the timer is only a safety net.

Full detail (polling cadence, stale-echo detection, what to do when a slot is
blocked vs. idle): **`references/heartbeat-loop.md`**.

## Mental model: distributed VCS

Treat the fleet like a team using a shared repo:

- **Workers are contributors.** Each works on its own branch in its own
  worktree, commits CODE ONLY to that branch, and never touches the integration
  branch or another worktree.
- **Terry is the maintainer.** It is the only actor that merges, and it always
  verifies in the canonical checkout before accepting a merge.
- **The integration branch is "main."** It is the single merge point; nothing
  edits it directly except Terry's merges and the state-file commits.
- **The queue is the backlog.** Priority-ordered blockers waiting for a free
  slot.

Isolation and merge rules (worktree setup, symlinking deps, never `git clean`,
conflict resolution): **`references/worktree-merge-protocol.md`**.

## Worked example: one tick

State before the tick — one worker in flight, two queued:

```jsonc
// agent_queue.json (excerpt)
"integration_head": "a1b2c3d",
"in_flight": [
  { "id": "stage3-warmup", "agent": "agent-7", "wt": "../wt-stage3",
    "branch": "terry/stage3-warmup", "port": "8801", "run": "baseline-config",
    "title": "warm up to threshold 24 before stage-3 exit; resume cp_pre_stage3; next: pass stage-3 boundary checks" }
],
"queue": [
  { "prio": 1, "id": "fast-path-check", "title": "threshold-24 fast path — confirm it clears stage 4 in one pass" },
  { "prio": 2, "id": "stage5-routing",  "title": "stage-5 dependency routing" }
]
```

The tick:

1. **OBSERVE** — completion notification fires for `stage3-warmup`. Poll
   `http://127.0.0.1:8801/state` to confirm it is genuinely done (not a stale
   echo): the progress metric reads 24, branch `stage3-warmup` has commits.
2. **INTEGRATE** — `git merge stage3-warmup` into the integration branch; run
   `uv run pytest tests/` in the main checkout → 168 pass → commit.
3. **DEQUEUE + DISPATCH** — pop `prio:1 fast-path-check`; `git worktree add -f
   -b fast-path-check ../wt-fastpath <new-integration-HEAD>`; symlink `deps`; copy
   the needed `cp_*.ckpt`; dispatch one worker on `--http-port 8802` with the
   dispatch-prompt contract (`templates/dispatch-prompt.md`).
4. **RECORD** — move `stage3-warmup` to `done_this_session`; add the new
   `fast-path-check` `in_flight` entry; bump `integration_head`; commit the
   state file.
5. **RE-ARM** — `ScheduleWakeup` with a long fallback; yield until the next
   completion or timer.

## Quick start

1. **Init the queue file** from the template:

   ```bash
   mkdir -p tools
   cp skills/terry/templates/agent_queue.json tools/agent_queue.json
   # edit integration_head, seed `queue` with your prioritized blockers
   git add tools/agent_queue.json && git commit -m "terry: init queue"
   ```

2. **Dispatch the first worker** — create its isolated worktree off the current
   integration HEAD, then dispatch one Agent (`run_in_background`) using the
   dispatch-prompt contract:

   ```bash
   HEAD_SHA=$(git rev-parse --short HEAD)
   git worktree add -f -b worker-1 ../wt-worker-1 "$HEAD_SHA"
   ln -sfn "$PWD/deps" ../wt-worker-1/deps          # symlink heavy untracked deps
   cp checkpoints/cp_seed.ckpt ../wt-worker-1/checkpoints/cp_seed_worker1.ckpt   # UNIQUE untracked name
   ```

   Fill `templates/dispatch-prompt.md` (scope, worktree path, branch, unique
   `--http-port`, determinism bar, report-back contract) and pass it to the
   Agent tool.

3. **Arm the heartbeat** — schedule the manager loop with a long fallback delay
   (`ScheduleWakeup` or `/loop`). Completions wake Terry sooner; the timer just
   guarantees forward progress if nothing reports in.

## References

- `references/heartbeat-loop.md` — the 5-step loop in depth: polling, stale-echo
  detection, blocked-vs-idle slots, re-arming.
- `references/worktree-merge-protocol.md` — worktree isolation, symlinks,
  manager-only merges, conflict resolution, verify-in-main.
- `references/lessons-and-antipatterns.md` — orphaned runs, resource wall,
  handle/port collisions, stale-base regression, tooling false-negatives,
  verify-before-claim, parallel-hypotheses-when-stuck.

## Templates

- `templates/agent_queue.json` — the priority-queue state file shape.
- `templates/dispatch-prompt.md` — the worker dispatch-prompt contract.
