# Worktree Isolation + Manager-Only Merge Protocol

The two halves of Terry's distributed-VCS discipline:

1. **Worktree isolation** — every worker runs in its OWN git worktree on its OWN
   branch, branched off the CURRENT integration HEAD, with a UNIQUE resource
   handle. Workers commit CODE ONLY to their branch and never touch the
   integration branch or another worktree.
2. **Manager-only merge** — ONLY the manager merges worker branches into the
   integration branch, ALWAYS verifies the test/verify suite IN THE MAIN
   checkout, resolves conflicts by fixed rules, and records every decision in the
   `done_this_session` ledger.

Treat the fleet exactly like distributed VCS: many isolated clones (worktrees),
one merge point (integration branch), one merger (the manager).

---

## 0. Vocabulary

| Term | Meaning |
|------|---------|
| **integration branch** | The merge point. What the team calls "main". NOTHING edits it directly except the manager's merges. (The *literal* `main` branch may be far behind — the project lives on the integration branch.) |
| **integration HEAD** | The current tip sha of the integration branch. New worktrees branch off THIS, not stale `main`. |
| **worktree (WT)** | An isolated working dir for one worker, on its own branch. `checkpoints/`/CWD-relative state is isolated per worktree. |
| **handle / port** | A unique resource the worker owns (e.g. `--http-port 8804`). No two live workers share one. |
| **main checkout** | The primary repo working dir where the manager runs the test suite to verify a merge. NOT a worktree. |
| **ledger** | `done_this_session` in the queue JSON — newest-first, dated, one line per merge/decision. |

---

## 1. Worktree Isolation Protocol

### 1.1 Create the worktree off the CURRENT integration HEAD

NEVER branch off stale `main`. Capture the integration HEAD first, then branch
off it. This prevents stale-base regression (a worker re-introducing or
duplicating already-merged work).

```bash
# From the MAIN checkout, on the integration branch:
INTEGRATION_BRANCH=integration
git checkout "$INTEGRATION_BRANCH"
git pull --ff-only          # ensure local integration HEAD is current
INTEGRATION_HEAD=$(git rev-parse --short HEAD)
echo "integration HEAD = $INTEGRATION_HEAD"

# Per-run worktree, on its own branch, OFF THE CURRENT INTEGRATION HEAD:
RUN=solver-alpha
BRANCH=feat-stage5-retry
WT=../sim_alpha_wt          # sibling dir, NOT nested inside the repo
git worktree add -f -b "$BRANCH" "$WT" "$INTEGRATION_HEAD"
```

- `-b "$BRANCH"` creates the worker branch.
- `-f` forces creation even if the path was used before (lets you re-dispatch a
  run into a fresh-but-same-named worktree without manual cleanup).
- The final arg is the **start point** — pin it to `$INTEGRATION_HEAD`
  explicitly. Do NOT omit it (that would branch off whatever HEAD happens to be).

Verify it landed where you expect:

```bash
git worktree list
git -C "$WT" rev-parse --short HEAD     # == $INTEGRATION_HEAD
git -C "$WT" rev-parse --abbrev-ref HEAD # == $BRANCH
```

### 1.2 Symlink large untracked dependencies (don't copy)

Heavy untracked deps (datasets, vendored binaries, model weights — e.g. the 673M
`deps/`) are SYMLINKED into the worktree, never copied. Copying wastes disk and
drifts; symlinking shares one ground-truth blob.

```bash
REPO=/Users/rubark/github/example/sim-engine
ln -sfn "$REPO/deps" "$WT/deps"
```

- `ln -sfn`: `-s` symbolic, `-f` replace an existing link, `-n` treat an existing
  link-to-dir as a file so it's replaced rather than nested inside.
- Confirm: `ls -l "$WT/deps"` shows `deps -> $REPO/deps`.

### 1.3 Seed checkpoints as UNIQUELY-named UNTRACKED files

A worker resumes from a checkpoint (snapshot, fixture). Copy needed checkpoints
into the worktree's state dir with a UNIQUE name so a `git checkout`/`reset`
inside the worktree never clobbers them, and sibling worktrees never collide.

```bash
# CWD-relative state dir is isolated per worktree (e.g. checkpoints/):
cp "$REPO/checkpoints/cp_stage4.ckpt" "$WT/checkpoints/cp_stage5_retry_resume.ckpt"
```

- Unique name (`cp_stage5_retry_resume`, not `cp_stage4`) → no cross-run clobber.
- Keep them UNTRACKED. They are tooling inputs, not deliverables — do not commit
  bulky binary states to the worker branch.

### 1.4 NEVER `git clean` a worktree

`git clean` deletes untracked files — which here means the symlinked `deps/`
link and the seeded `cp_*.ckpt` checkpoints. One `git clean -fdx` wipes a
worker's entire ability to run.

```bash
# FORBIDDEN inside any worktree:
#   git clean -fd
#   git clean -fdx
#   git clean -x
```

To discard tracked-file edits, use a SCOPED reset instead, which leaves
untracked deps/checkpoints intact:

```bash
git -C "$WT" checkout -- path/to/file.py     # revert one tracked file
git -C "$WT" reset --hard "$BRANCH"          # reset tracked tree only; untracked survive
```

### 1.5 One agent per worktree; unique handle per worker

- **Exactly one worker agent per worktree at a time.** Two agents in one worktree
  collide on shared files and the handle. If a run needs re-dispatch, let the old
  agent finish/die first, or give the new one a fresh worktree.
- **Every worker gets a UNIQUE handle/port** so siblings never collide. Match the
  port to the run in the queue's `in_flight[].port`.

```bash
# Launch the worker process bound to its own handle, from its worktree,
# using the MAIN .venv interpreter (one toolchain, isolated state):
"$REPO/.venv/bin/python" -u "$WT/run_sim.py" \
    --http-port 8804 --metrics --max-steps 15000000 \
    > /tmp/sim_validate_alpha.log 2>&1 &
```

- `--http-port 8804` is THIS worker's handle. No other live worker may use 8804.
- Use the MAIN `.venv` interpreter (`$REPO/.venv/bin/python`) — the worktree
  shares the toolchain; only CWD-relative state is isolated.

### 1.6 Verify exactly one process per handle (kill orphans)

A finished agent that relaunched a run can leave an orphan holding its port; the
next worker reusing that port collides (two processes, one handle). Before
dispatching onto a handle, assert it's free; scope every kill to the handle (or
the run name) — NEVER broad-kill the binary (that nukes siblings).

```bash
# Inspect: who owns 8804?
pgrep -fa "http-port 8804"

# SCOPED kill — only this handle's orphan:
pkill -f "http-port 8804"

# FORBIDDEN — kills every sibling run:
#   pkill -f run_sim.py
```

### 1.7 Worktree teardown (after the branch is merged)

Once the manager has merged and verified the branch, retire the worktree
cleanly (this does NOT delete the symlink target or the main checkout):

```bash
git worktree remove "$WT"            # refuses if dirty; finish/commit first
# or, if the dir is already gone:
git worktree prune
git branch -d "$BRANCH"              # delete the merged worker branch
```

Do NOT `rm -rf` the worktree dir manually — that leaves a dangling worktree
registration. Use `git worktree remove` / `prune`.

---

## 2. Manager-Only Merge Protocol

Workers commit CODE ONLY to their own branch. The manager is the SOLE merger into
the integration branch. The non-negotiable verify step runs in the MAIN checkout.

### 2.1 Worker side: commit code-only to the worker branch

The worker, in its own worktree, stages CODE files only (e.g. `run_sim.py`,
`core/`) — never the integration branch, never bulky checkpoints, never another
worktree's files.

```bash
git -C "$WT" add run_sim.py core/
git -C "$WT" commit -m "stage-5 retry: reseed-and-retry around the transient solver lock"
# push optional; the manager can merge a local branch directly.
```

The worker then reports back (see §3). The worker NEVER runs `git merge` into the
integration branch and NEVER checks out the integration branch.

### 2.2 Manager side: merge the worker branch into integration

From the MAIN checkout, on the integration branch:

```bash
cd "$REPO"
git checkout "$INTEGRATION_BRANCH"
git pull --ff-only                      # current integration HEAD

# Merge the completed worker branch (a no-ff merge keeps a readable topology;
# fast-forward is fine when the branch is strictly ahead).
git merge --no-ff "$BRANCH" -m "MERGE $BRANCH: <one-line summary of what it does>"
```

If the worker pushed to a remote instead of leaving a local branch:

```bash
git fetch origin "$BRANCH"
git merge --no-ff "origin/$BRANCH" -m "MERGE $BRANCH: <summary>"
```

### 2.3 Resolve conflicts by FIXED rules

Resolve deterministically — no ad-hoc judgment — and record the decision (§2.5):

1. **Distinct additions at the same spot (two unrelated new things) → KEEP BOTH.**
   Two workers each added a helper / a callsite / a config entry near the same
   line: include both hunks; reconcile import/order so the file still parses.
2. **Competing implementations of the SAME fix → KEEP THE VALIDATED / MORE
   COMPLETE ONE, drop the duplicate.** Two workers each implemented "fix the
   stage-5 stall": keep the one with passing evidence (determinism MD5, test
   count, convergence reached) and the broader coverage; delete the other. Record
   which won and why.
3. **One side is a stale-base re-introduction of already-merged work → DROP the
   stale side, keep integration's current version.** (This is why workers branch
   off CURRENT HEAD — but reconcile here if it still happens.)

```bash
# After editing conflicted files to apply the rule above:
git add <resolved-files>
git commit --no-edit        # completes the merge with the prepared message
```

### 2.4 ALWAYS verify in the MAIN checkout (never the worktree)

A worktree shows SPURIOUS failures from incomplete fixtures/state — its test
count is NOT trustworthy. Run the suite in the MAIN checkout, post-merge, and
commit/keep the merge ONLY if green.

```bash
cd "$REPO"
uv run pytest tests/        # expected: full green (e.g. 168 passed)
```

- Green → the merge stands; proceed to RECORD (§2.5) and bump
  `integration_head`.
- Red → the merge is NOT acceptable. Either fix forward on the integration branch
  (small, obvious reconciliation) or back the merge out and bounce the branch to
  the worker:

```bash
# Back out the just-made merge commit if it can't be made green quickly:
git reset --hard ORIG_HEAD
```

NEVER record a merge as done on the strength of a worktree's pytest output.

### 2.5 RECORD the merge in the ledger + bump integration_head

Every merge gets a newest-first, dated ledger line in `done_this_session`,
including: branch + new sha, what it does, conflict decisions, and the
verification evidence (test count + determinism hash). Then update
`integration_head`.

```bash
NEW_HEAD=$(git rev-parse --short HEAD)
# Edit tools/agent_queue.json:
#   - set "integration_head" = "$NEW_HEAD"
#   - prepend to "done_this_session":
#       "MERGED feat-stage5-retry (<sha>, N commits, K conflicts resolved:
#        kept alpha's reseed path, dropped bravo's dup BFS): <summary>.
#        Determinism MD5 <hash>, 168 tests. Next blocker = <...>."
git add tools/agent_queue.json
git commit -m "queue: merge feat-stage5-retry; integration_head=$NEW_HEAD"
```

Then retire the worktree/branch (§1.7) and dispatch the next blocker.

---

## 3. Worker Report-Back Contract (merge inputs the manager needs)

So the manager can merge + verify without re-deriving everything, each worker
reports back:

- **What worked, with EVIDENCE** — the end-state fact (a flag/memory/output line),
  not just "done". (e.g. "stage 5 converged, status flag DONE=0x01, 0 residual
  errors".)
- **Commit hash(es)** on the worker branch.
- **Determinism proof** — fixed/bounded budget + two byte-identical output hashes
  (MD5). Divergence is NEVER "flaky" — it's a real branch/change.
- **How far it got + the next blocker** — so the manager can queue the follow-on.

The manager VERIFIES the evidence line against ground truth before recording a
merge as a win — do not trust a "done" without the flag/output.

---

## 4. End-to-End Checklist

Dispatch one worker:

- [ ] `git checkout "$INTEGRATION_BRANCH" && git pull --ff-only`; capture `$INTEGRATION_HEAD`.
- [ ] `git worktree add -f -b "$BRANCH" "$WT" "$INTEGRATION_HEAD"`.
- [ ] `ln -sfn "$REPO/deps" "$WT/deps"`.
- [ ] Copy needed checkpoints into `"$WT"` under UNIQUE untracked names.
- [ ] Assert handle free (`pgrep -fa "http-port NNNN"`); pick a UNIQUE port.
- [ ] One agent only; it commits CODE ONLY to `"$BRANCH"`.

Merge one completed worker:

- [ ] `git checkout "$INTEGRATION_BRANCH" && git pull --ff-only`.
- [ ] `git merge --no-ff "$BRANCH"`; resolve conflicts by the FIXED rules (§2.3).
- [ ] **`uv run pytest tests/` IN THE MAIN CHECKOUT** — green or back it out.
- [ ] Verify the worker's evidence line against ground truth.
- [ ] Prepend the dated ledger entry; bump `integration_head`; commit the queue.
- [ ] `git worktree remove "$WT"` + `git branch -d "$BRANCH"`.

---

## 5. Anti-Patterns (do not do these)

- **Branching off stale `main`** → stale-base regression (re-introduces/duplicates
  merged work). Always branch off the CURRENT integration HEAD.
- **`git clean` in a worktree** → deletes the `deps` symlink + seeded checkpoints.
  Use scoped `checkout --`/`reset --hard <branch>` instead.
- **Trusting a worktree's pytest count** → spurious fixture failures. Verify ONLY
  in the MAIN checkout.
- **A worker merging into / checking out the integration branch** → only the
  manager merges. Workers are code-only on their own branch.
- **Reusing a handle without checking** → orphan + new worker collide on one port.
  `pgrep`/scoped `pkill` first.
- **Broad `pkill -f <binary>`** → nukes every sibling run. Scope kills to the
  handle or run name.
- **Two agents in one worktree** → file/handle collisions. One agent per worktree.
- **Copying heavy deps instead of symlinking** → disk bloat + drift. `ln -sfn`.
- **Recording a merge as done without verifying the evidence line** → false wins.
  Read the flag/output before claiming success.