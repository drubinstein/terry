---
name: jamie
description: Invoke when you have a bug report or issue and need to confirm it's REAL before anyone fixes it — turn the report into a precise claim, faithfully recreate the reporter's conditions (the version they hit, config, data, platform, timing), build a minimal reliable reproduction, quantify how often it fires, and return a verdict: CONFIRMED / PLAUSIBLE / BUSTED. Use when triaging an issue, when "can't reproduce" / "works on my machine", when a failure is intermittent or flaky, or before assigning, fixing, or closing a bug. The reproduce-before-you-believe step upstream of root-causing.
---

# Jamie — replicate the report to confirm the bug

> *The claim · the rig · the verdict.*

Jamie takes a **bug report** and tries to make it happen — on purpose, reliably —
**before** anyone tries to fix it. A report is a *claim*, not a fact: "the app
crashes when I upload a CSV" is a hypothesis until you can pull the trigger
yourself. Jamie's job is to convert that claim into a **minimal, reliable
reproduction** and stamp it with a verdict, Mythbusters-style:

- **CONFIRMED** — reproduced reliably; you hold a minimal, one-command repro (and a
  reliability rate if it's intermittent).
- **PLAUSIBLE** — reproduces only under conditions you had to *discover*, or a real
  adjacent defect exists but not the exact report.
- **BUSTED** — could not reproduce after faithfully recreating the conditions *and*
  escalating. **Not** "there's no bug" — "the report **as written** doesn't
  reproduce" — and you say *why*.

The whole discipline rests on one rule: **a failed reproduction is evidence about a
mismatched condition, not proof the reporter is wrong.** Most "can't reproduce" is
one unmatched variable — the wrong version, the wrong data, the wrong platform, the
wrong timing — away from a perfect repro.

Six moves:

- **The report is a claim.** Turn the prose into a *falsifiable* statement: exact
  preconditions, steps, expected vs actual, and the environment it was seen in.
  Write down what the report **doesn't** say (the unstated conditions).
- **Match their world, not yours.** Recreate the **version they hit** (checkout that
  release/commit, *not* latest), their config/flags, their data/inputs, their
  platform/OS/arch, locale/timezone, account/permissions/state, concurrency/scale.
- **Build the rig and capture the failure.** Reproduce the full scenario until it
  fails, and capture the failure as an **artifact** (a log, a crash, a diff) — not
  "I think I saw it."
- **Minimize.** Shrink the working repro to the *smallest* thing that still fails
  (delete-and-retest). The deliverable is a repro someone else can run in one step.
- **Quantify reliability.** 100% or intermittent? Run it N times and report the
  **rate** (e.g. 7/20). Intermittent is a *number*, not a shrug.
- **Never bust on the first miss.** Before declaring BUSTED, **escalate**: vary the
  condition you most likely mismatched, ask the reporter for the one missing
  variable, and check whether it's already been fixed.

## When to use

- **triaging an incoming issue / bug report** before any work starts
- **"can't reproduce it" / "works on my machine"** — the maintainer's side of that
- an **intermittent / flaky / "happens sometimes"** report
- before **assigning, fixing, or closing** a bug (close as *not-repro* only with
  evidence and a stated reason)
- you want a **minimal repro** or a **failing regression test** to anchor the fix
- confirming a **security report** or a **customer escalation** is real before you
  spend a team on it

## When NOT to use

- The bug is **already reproducing reliably** in front of you — you have the repro;
  skip to root-cause (`sherlock`) or just fix it.
- It's **your own freshly-written code** failing **your own** test — that's plain
  debugging; the repro is already in hand → debug it directly
  (`superpowers:systematic-debugging` / `sherlock`).
- You're confirming **your own work is complete** — that's the opposite direction;
  use `superpowers:verification-before-completion`.
- A **feature request / design discussion** — there's no defect to replicate.
- You can already trigger it on demand and only need to know **why it's flaky** —
  that's `sherlock`. Jamie's job ends once `k/N` is a runnable gate; explaining the
  *mechanism* is sherlock's.

## The replication loop (claim → rig → verdict)

1. **EXTRACT THE CLAIM.** Rewrite the report as a falsifiable claim: *preconditions
   · steps · expected · actual · environment-seen-in*. Mark every **unstated
   condition** (version? data? platform? scale? account?) — those gaps are your
   first work, because they're where "can't reproduce" hides.
2. **MATCH THE CONDITIONS.** Recreate the reporter's world deliberately, highest-
   leverage variables first: the **version they actually hit** (not `main`), config
   & feature flags, the **real input/data** (theirs, or a faithful synthetic),
   platform/OS/arch, locale/timezone, account/permissions/pre-existing state,
   concurrency/load/scale, network. (Dimension checklist + why each matters:
   `references/cant-reproduce-playbook.md`.)
3. **BUILD THE RIG, FAIL IT, MINIMIZE, QUANTIFY.** Reproduce the full scenario and
   **capture the failure artifact**. Then **minimize** to the smallest reliable
   repro (delete-and-retest each element). Then **quantify**: run it N times and
   record the rate — `k/N`. The output is a one-command repro + its reliability.
4. **VERDICT + HANDOFF.**
   - **CONFIRMED** → reliable minimal repro in hand → hand it to `sherlock`
     (find the cause) and/or `andrej` (drive the fix — the repro is the gate).
   - **PLAUSIBLE** → reproduces only under discovered conditions, or an adjacent
     defect is real → document the conditions; narrow further or hand off with
     caveats.
   - **BUSTED** → faithful recreation **and** escalation both failed → classify
     *why* (already-fixed / user-error / env-specific-to-reporter / missing-info /
     below-threshold-intermittent / misdescribed) and return the evidence + the one
     **missing variable** you need from the reporter. Never bust on the first miss.

Full detail (claim extraction, the condition-match checklist, minimization,
measuring intermittency, the escalation ladder before BUSTED):
**`references/replication-method.md`**. Verdict definitions and evidence bars:
**`references/verdict-rubric.md`**.

## Mental model: Mythbusters

- **The claim, the rig, the verdict.** You don't "look into" a report — you build a
  controlled rig that recreates it, run it, and rule it confirmed / plausible /
  busted *with evidence on tape*.
- **If it ain't reproduced, it ain't a bug yet — it's a claim.** Confirmation is a
  repro you can run on demand, not a story that sounds plausible.
- **Replicate the conditions, not your assumptions about them.** "It crashes on
  upload" — *which version, which file, how big, what encoding?* You match the
  reporter's actual world; you don't substitute the convenient one.
- **BUSTED is a verdict about the report, not the reporter.** It means "as written,
  this doesn't reproduce — here's what I tried and the variable I'm missing," never
  "you're wrong."

## Worked example: the CSV crash that "works on my machine"

**Report:** *"App crashes whenever I upload a CSV."*

1. **EXTRACT.** Claim = "uploading a CSV crashes the app." Unstated conditions:
   **which version? which CSV (size/encoding/content)? which platform?** That's the
   whole ballgame.
2. **First naive attempt (the trap).** On `main` with a tidy 100-row sample CSV →
   works fine. The tempting move is **BUSTED**. Don't — you matched *none* of the
   reporter's conditions.
3. **MATCH.** The report was filed against **v2.3.1** (you were on `main`, where it
   may already be fixed), and the reporter's file is a **1.2 M-row** export with a
   **UTF-8 BOM** and **CRLF** line endings. Rebuild the rig: `git checkout v2.3.1`,
   generate a CSV with BOM + CRLF at 1.2 M rows, upload → **crash** (OOM in the
   parser).
4. **MINIMIZE.** Delete-and-retest: BOM removed → still crashes (not it). CRLF → LF
   → still crashes (not it). Drop to 100k rows → no crash; crashes reliably above
   ~800k rows. **Minimal repro:** *"on v2.3.1, upload a ≥800k-row CSV."*
5. **QUANTIFY.** 20/20 crashes at 1.2 M rows — deterministic.
6. **VERDICT: CONFIRMED.** And a key note for handoff: it does **not** reproduce on
   `main` → likely already fixed (find the commit and verify; if so the fix is
   "backport / upgrade," not a new patch). Hand the minimal repro to `sherlock`
   (cause: unbounded in-memory parse) / `andrej` (gate: crash-free at 2 M rows).

The lesson: the first "works for me" was a **version + data mismatch**, not a busted
report. A real, deterministic bug was one matched condition away.

## Quick start

1. **Open a repro report** and extract the claim — *and the unstated conditions*:

   ```bash
   cp skills/jamie/templates/repro-report.md repro-report.md
   # fill: preconditions · steps · expected · actual · environment; list what the report DOESN'T say
   ```

2. **Match the reporter's conditions** — the **version they hit** first, then config,
   the real data, platform, locale/tz, account/state, scale/timing (the dimension
   checklist + why each one breaks repro: `references/cant-reproduce-playbook.md`).

3. **Build the rig → fail it → minimize → quantify.** Capture the failure artifact,
   shrink to a one-command repro, run it N times for a `k/N` reliability rate.

4. **Stamp the verdict.** CONFIRMED / PLAUSIBLE / BUSTED (definitions + evidence bar:
   `references/verdict-rubric.md`) — **never BUSTED on the first miss; escalate
   first.** Hand a CONFIRMED minimal repro to `sherlock` / `andrej`.

## References

- `references/replication-method.md` — the loop in depth: extracting a falsifiable
  claim from prose, the condition-match strategy (highest-leverage variables first),
  building & minimizing the repro, measuring intermittency (`k/N`, and how many runs
  you need), and the escalation ladder you must climb before declaring BUSTED.
- `references/cant-reproduce-playbook.md` — the catalogue of **why a real bug won't
  reproduce for you**, as Symptom → likely-mismatch → fix, across every condition
  dimension (version/build, config, data, platform/arch, locale/timezone,
  concurrency/scale, state/ordering, cache, network, permissions, the reporter's
  specific account, Heisenbug-under-observation, already-fixed-on-`main`,
  only-in-prod).
- `references/verdict-rubric.md` — CONFIRMED / PLAUSIBLE / BUSTED: the precise
  definition and **evidence bar** for each, the sub-classes of BUSTED (already-fixed
  / user-error / env-specific / missing-info / below-threshold / misdescribed-but-
  adjacent), and the correct handoff for each verdict.

## Templates

- `templates/repro-report.md` — a fill-in: the extracted claim (preconditions ·
  steps · expected · actual · env), the conditions matched vs unmatched, the minimal
  one-command repro, the reliability rate `k/N`, the verdict + its evidence, and the
  handoff (to `sherlock`/`andrej`, or back to the reporter for the one missing
  variable).

## Relationship to sherlock, andrej, systematic-debugging & terry

Jamie is the **reproduce-before-you-believe** front door; it produces the artifact
the other skills consume:

- **`sherlock`** answers *"why?"*; Jamie answers *"is it real, and how do I trigger
  it?"* — the step **before** sherlock. A **CONFIRMED minimal repro is the input to
  sherlock's** elimination (and the thing that lets you eliminate by *evidence*).
- **`andrej`**'s "reproduce the failure before you fix it" is a single line; Jamie is
  that step expanded into a discipline. Jamie's confirmed repro **and its reliability
  rate** become `andrej`'s metric/gate (e.g. `failures_per_20_runs: 7 → 0`).
- **superpowers:systematic-debugging** is the overall reproduce → isolate → fix flow;
  Jamie is its **reproduction stage** — so if you *already* hold a reliable repro,
  enter systematic-debugging (or `sherlock`) directly and skip Jamie. A CONFIRMED
  repro converts directly into the **failing regression test** TDD wants written first.
- **`terry`**: at fleet scale, Jamie is the **issue-queue triage** — confirm or bust
  each inbound report, then dispatch the CONFIRMED ones (each with its minimal repro)
  as scoped worker tasks.
