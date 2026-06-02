# The verdict rubric — CONFIRMED / PLAUSIBLE / BUSTED

Every investigation ends in exactly one verdict, backed by evidence. The verdict is
about **the report**, not the reporter — and each verdict has a required evidence
bar and a correct handoff.

## CONFIRMED

**Definition:** you reproduced the reported failure and hold a **minimal repro you
can run on demand**, with a known reliability.

**Evidence bar:**
- a one-command (or few-step) minimal reproduction someone else can run, AND
- the captured failure artifact (stack trace / wrong output / crash) matching the
  reporter's **exact** symptom (not a lookalike), AND
- a reliability rate: `N/N` deterministic, or `k/N` with the amplifying condition
  noted.

**Handoff:** the repro is the asset. Pass it to **`sherlock`** (root-cause by
elimination — the minimal repro pre-eliminates suspects) and/or **`andrej`** (drive
the fix; the repro's pass/fail is the gate, e.g. `failures_per_20_runs: k → 0`).
Convert it into a **failing regression test** first (TDD), so the fix is provably
anchored.

> Sub-note — **CONFIRMED-but-already-fixed:** reproduces on the reporter's version,
> green on `main`. Still CONFIRMED (the bug was real). Find the fixing commit; the
> action is **backport / tell them to upgrade**, plus a regression test if one is
> missing.

## PLAUSIBLE

**Definition:** the report points at a real defect, but you can't (yet) reproduce it
*as written* — you reproduced it only under **conditions you had to discover**, or
you found a **real adjacent bug** that may or may not be what they hit.

**Use it when:**
- it reproduces only under a narrow condition you inferred (a specific scale, a race
  you had to amplify) and you're not yet sure that condition matches the reporter's,
- OR the symptom reproduces intermittently below a rate you can pin down,
- OR you found a genuine bug in the same area but can't tie it to the report.

**Evidence bar:** the discovered conditions + whatever partial repro you have +
explicitly what's still unconfirmed (the gap between "what I reproduced" and "what
they reported").

**Handoff:** document the conditions; either narrow toward CONFIRMED (sweep the
uncertain variable), or hand off with the caveat stated, or go back to the reporter
to confirm the discovered condition matches their case. Don't inflate PLAUSIBLE to
CONFIRMED — the missing tie is real information.

## BUSTED

**Definition:** after a **faithful recreation** of the reported conditions **and** a
climbed escalation ladder, the report **as written does not reproduce.** This is a
verdict about the report, never "the reporter is wrong" or "there is no bug" in the
universe — it's "this description, reproduced faithfully, does not fail, and here is
what I tried."

**Evidence bar (mandatory):** BUSTED is a *claim you must support*, exactly like
CONFIRMED:
- the conditions you matched (version, data, platform, scale, …) — show you didn't
  test the convenient case, AND
- how many times / how hard you tried (e.g. "100 runs at 4× parallelism, their
  v2.3.1, their file"), AND
- the **sub-class** (below) + the **one missing variable** you'd need to close it.

**Never BUSTED on the first miss.** One green run is not a verdict.

### BUSTED sub-classes — say which

| Sub-class | Meaning | Correct next step |
|-----------|---------|-------------------|
| **Already fixed** | Repros on their version, not on `main` | Reclassify as CONFIRMED-already-fixed; upgrade/backport. (Not really busted.) |
| **Needs info** | You can't match a condition you don't know | Ask the reporter the **one specific** missing variable (version / file / a fresh-profile check). Leave open, don't close. |
| **User error / works-as-designed** | The behavior is correct; expectation was wrong | Explain the expected behavior with evidence; consider a docs/UX fix so others don't hit it. |
| **Environment-specific to reporter** | Real for them, tied to their local env (corrupt install, extension, proxy, hardware) | Help them isolate (fresh profile/container); fix if it's a robustness gap, else document. |
| **Below-threshold intermittent** | Possibly real but under your detection rate | State the runs done and the rate ceiling; amplify or ask for their frequency before closing. |
| **Misdescribed but adjacent** | The literal report is wrong, but you found a real nearby bug | File/handle the real bug; close the original as superseded, linked. |

## Anti-patterns (verdict integrity)

- **Premature BUSTED** — "couldn't repro in 5 minutes on `main`." That's an unmatched
  version + an unmeasured rate, not a verdict.
- **Green-run-as-proof** — "I ran it once and it worked, so BUSTED." A passing run on
  the *convenient* case (latest build, a clean test file) is evidence of nothing
  about a report filed on another version/file. For destructive symptoms (corruption,
  data loss), "it opened" ≠ "the data is intact" — verify the exact artifact the
  reporter says is damaged.
- **Confirmation by anecdote** — "yeah I think I saw it too." No artifact, no
  CONFIRMED.
- **Symptom lookalike** — you reproduced *a* crash, not *their* crash. Match the
  exact artifact.
- **Silent close** — closing "cannot reproduce" with no conditions tried and no
  missing-variable ask. Includes the **"close enough" close**: matching *most*
  conditions (their version, 50 runs) but on a *similar*, not the *actual*, input —
  matching most conditions is not matching the load-bearing one. Every BUSTED states
  what you tried and what you need.
- **Inflated CONFIRMED** — calling a one-off, unminimized, unmeasured failure
  CONFIRMED. Minimize and quantify first, or it's PLAUSIBLE.
