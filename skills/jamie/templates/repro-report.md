# Repro report — <ISSUE # / ONE-LINE TITLE>

> Copy per bug report. Goal: turn the report into a **minimal, reliable repro** and
> a verdict (**CONFIRMED / PLAUSIBLE / BUSTED**) backed by evidence. Match the
> reporter's conditions before concluding anything; never stamp BUSTED on the first
> miss. See `references/replication-method.md` and `references/verdict-rubric.md`.

## 1. The claim (extracted from the report)

- **Preconditions:** <state that must exist first>
- **Steps:** <exact ordered sequence>
- **Expected:** <what should happen>
- **Actual:** <the precise failure — exit code / exception / wrong value / hang>
- **Environment seen in:** <version/build · OS/arch · browser/device · region>
- **Unstated conditions (what the report does NOT say — answer these):**
  - version? <> · data/input? <> · platform? <> · scale? <> · account/state? <> · locale/tz? <>

## 2. Conditions matched (their world, not yours)

| Dimension | Reporter's value | Matched? | Notes |
|-----------|------------------|----------|-------|
| Version / build (their exact tag, NOT main) | | ☐ | |
| Config / feature flags | | ☐ | |
| Data / input (size, encoding, edge values) | | ☐ | |
| Platform / OS / arch | | ☐ | |
| Locale / timezone / clock | | ☐ | |
| Account / permissions / pre-existing state | | ☐ | |
| Concurrency / load / scale | | ☐ | |
| Network / environment | | ☐ | |

## 3. The rig → fail → minimize → quantify

- **Failure artifact captured:** <paste/link the stack trace / crash / wrong output — matches their EXACT symptom?>
- **Minimal reproduction (delete-and-retest down to the smallest failing case):**

  ```bash
  # one command / fewest steps, smallest input
  <repro command>
  ```

- **What was minimized away (irrelevant):** <elements removed that didn't change the failure — each is a pre-eliminated suspect for sherlock>
- **Reliability:** <k/N runs, e.g. 18/20> · deterministic? <y/n> · amplifier used (load/seed/latency): <>

## 4. Escalation (required before any BUSTED)

- [ ] Re-read report for a missed detail (version, attachment, error code, screenshot locale)
- [ ] Varied the most-likely-mismatched condition: <which + result>
- [ ] Checked already-fixed: repros on <their version>? green on `main`? <result>
- [ ] Amplified timing/scale if intermittent (ran 100×, added load): <result>
- [ ] If still stuck — the ONE specific question for the reporter: <e.g. "what version / can you attach the file / does it happen in a fresh profile?">

## 5. Verdict

- **Verdict:** ☐ CONFIRMED  ☐ PLAUSIBLE  ☐ BUSTED
- **Evidence:** <minimal repro + artifact + k/N  — OR  conditions tried + runs done + missing variable>
- **If BUSTED, sub-class:** <already-fixed / needs-info / user-error / env-specific / below-threshold / misdescribed-but-adjacent>
- **Handoff:**
  - CONFIRMED → minimal repro to **`sherlock`** (root cause) / **`andrej`** (fix gate: `failures_per_N → 0`); write the failing regression test.
  - PLAUSIBLE → document discovered conditions; narrow the uncertain variable or confirm with reporter.
  - BUSTED → post the conditions tried + the one missing variable; leave *needs-info* open (don't silently close).
