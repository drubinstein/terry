# The replication method — in depth

The loop turns a prose report into a verdict-bearing artifact:

```
  1. EXTRACT the claim ──► 2. MATCH the conditions ──► 3. BUILD rig, FAIL, MINIMIZE, QUANTIFY
        (+ unstated)          (version first!)                       │
                                   ▲                                 ▼
                                   │                            reproduced?
                                   │              ┌──────────────┬───────────────┐
                                   │           yes (reliable)  yes (only if…)   no
                                   │              ▼               ▼              ▼
                                   │          CONFIRMED        PLAUSIBLE    escalate ──┐
                                   └──────────────────────────────────────────────────┘
                                       (vary a mismatched condition / ask reporter / check if fixed)
                                                                                  │
                                                                          still no after
                                                                          faithful + escalated
                                                                                  ▼
                                                                               BUSTED (+ why)
```

## 1. Extract the claim

A bug report is **prose written by someone with partial information**, often the
*symptom* rather than the *trigger*. Convert it to a falsifiable claim:

- **Preconditions** — what state must exist first (logged in as X, feature flag on,
  a record already present, N items in the cart)?
- **Steps** — the exact sequence, in order.
- **Expected vs Actual** — the precise discrepancy. "Crashes" → *what* crash (exit
  code, exception, hang, wrong value)?
- **Environment seen in** — version/build, OS/arch, browser, device, region.

Then the highest-value act: **list what the report does NOT say.** Reporters omit
the conditions they think are irrelevant — which are exactly the ones that differ
from your default. Every gap (version? data? scale? account? locale?) is a question
to answer in step 2, and a reason a naive attempt will "work for me."

> A report describes the reporter's *experience*; you must reconstruct the *system
> state* that produced it. Those are not the same thing.

## 2. Match the conditions

Recreate the **reporter's** world, not the one convenient to you. Order matters —
spend effort on the highest-leverage mismatches first:

1. **Version / build (do this first).** Reproduce against the **commit or release
   the reporter hit**, not `main`. Reproducing on latest risks a false BUSTED on a
   bug that's already fixed — or a false "works for me" the same way. `git checkout`
   the tag; match the lockfile/deps.
2. **Config & feature flags.** Their flags, env vars, plan/tier, limits — not your
   dev defaults.
3. **Data / inputs.** The actual input, or a *faithful synthetic*: same size,
   encoding (BOM? UTF-16?), shape, edge values, a poisoned record. "It works on a
   small clean sample" is not a test of a report filed on real data.
4. **Platform / OS / arch.** Linux vs macOS vs Windows, x86 vs ARM, container vs
   host, browser/version, mobile vs desktop.
5. **Locale / timezone / clock.** Decimal commas, RTL text, DST boundaries, a
   non-UTC server, a date near midnight UTC.
6. **Account / permissions / pre-existing state.** A specific user's data, a
   migrated-from-old-version row, a half-finished workflow, leftover state.
7. **Concurrency / load / scale.** A race needs *contention* — run it under
   parallelism, at the reporter's data volume, at production request rate. Many
   bugs are invisible below a threshold.
8. **Network / environment.** Latency, a proxy, TLS, DNS, a slow/flaky downstream.

Full Symptom → likely-mismatch → fix catalogue: `cant-reproduce-playbook.md`.

## 3. Build the rig, fail it, minimize, quantify

**Build & fail.** Stand up the matched scenario and reproduce the failure. **Capture
the failure as an artifact** — the stack trace, the crash dump, the wrong output, a
screen recording. "I think I saw it flicker" is not a reproduction; a saved artifact
is. If you can't capture it, you can't confirm it.

**Minimize.** A repro that requires the whole app is hard to hand off and hard to
root-cause. Shrink it by **delete-and-retest**: remove a step / a field / a config /
a data column and re-run. If the failure survives, that element was irrelevant —
drop it. Keep going until every remaining piece is load-bearing. The result is the
**minimal reproduction**: ideally one command, the smallest input, the fewest steps.
(This also pre-localizes the bug for `sherlock`: each removed element is an
eliminated suspect.)

**Quantify reliability.** Determinism is a property you *measure*, not assume:

- Run the minimal repro **N times** and record the rate, `k/N` (e.g. 7/20).
- **Deterministic** (N/N) → a clean gate for the fix.
- **Intermittent** (k/N) → that rate **is part of the repro**, and a real signal:
  intermittency points at timing/concurrency/ordering/uninitialized state. Make it
  *more* reproducible by amplifying the suspected condition (more parallelism, a
  stress loop, a fixed unlucky seed, injected latency) — raising k/N toward N/N both
  confirms the mechanism and gives a better gate.
- How many runs? Enough to distinguish "rare" from "never": if you expect ~5%, 20
  runs is a coin-flip to see it once — run 100+. (Rule of thumb: to be ~95% sure of
  seeing a bug that fires with probability `p` at least once, run ≈ `3/p` times —
  p=5% → ~60, p=1% → ~300; to *estimate* the rate, run several multiples of that.)
  Report what you ran; **"I ran it once and it passed" is not BUSTED.**

## 4. The escalation ladder (climb this before BUSTED)

A first failed reproduction means *you haven't matched a condition yet* — not that
the bug is fake. Before stamping BUSTED, climb:

1. **Re-read the report for a missed detail** — the version, a screenshot's
   timestamp/locale, an attached file, an error code you glossed over.
2. **Vary the most-likely-mismatched condition** — the one dimension from step 2 you
   couldn't pin down (data scale? exact version? platform?). Sweep it.
3. **Check if it's already fixed** — does it reproduce on the reporter's version but
   not on `main`? Then it's CONFIRMED-and-likely-fixed (find the commit; the fix is
   backport/upgrade), not BUSTED.
4. **Amplify** — if you suspect timing/concurrency, add load/parallelism/latency;
   run 100×, not 1×.
5. **Ask the reporter for the ONE missing variable** — a specific, cheap question
   ("what version?", "can you attach the file?", "does it happen in a fresh
   profile?"), not "can't repro, please advise."

Only after a **faithful recreation** and a **climbed ladder** both fail do you
declare BUSTED — and then you record *what you tried* and *the variable you're still
missing*, so the verdict is auditable and the reporter can close the gap. (Verdict
definitions and the BUSTED sub-classes: `verdict-rubric.md`.)
