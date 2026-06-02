# Case board — <ONE-LINE BUG TITLE>

> Copy per investigation. Rule: a suspect moves to **eliminated** ONLY with an
> evidence line that makes it *impossible* — never a "should / surely / trusted".
> A suspect you can't yet disprove stays **open**. When exactly one survives, it's
> the truth (however improbable) — confirm it. When ZERO survive, you over-
> eliminated (re-test an assumption) or under-enumerated (add the improbable).
> See `references/elimination-method.md`.

## 1. The facts (observe before theorizing)

- **Exact symptom:** <precise, e.g. "GET /x returns 200 with `ts` ~300s stale on ~3% of calls since Tue">
- **Reproduction:** <one-command repro, or the steps + frequency>
- **Hard evidence:** <logs / traces / failing diff / inputs / env>
- **Negative facts (the dog that didn't bark):** <what SHOULD appear and doesn't — a missing log line, an error that never fired, a metric that stayed flat>
- **Last-known-good:** <commit / time / env where it was correct — bounds the search>

## 2. The complete suspect list (include the improbable!)

Sweep every layer; probability is irrelevant here — completeness is.

| # | Suspect | Layer | Status (open / **eliminated** / SURVIVING) | Decisive falsifying test | Evidence (how it died, or result) |
|---|---------|-------|--------------------------------------------|--------------------------|-----------------------------------|
| 1 | | your code | open | | |
| 2 | | config / flags | open | | |
| 3 | | inputs / data | open | | |
| 4 | | build / toolchain | open | | |
| 5 | | dependency / library | open | | |
| 6 | | runtime / OS | open | | |
| 7 | | hardware / node | open | | |
| 8 | | environment / network / DNS / LB | open | | |
| 9 | | concurrency / timing / race | open | | |
| 10 | | state / caching (app/redis/CDN/client) | open | | |
| 11 | | clock / time / TZ | open | | |
| 12 | | the observer (test / repro / logging) | open | | |
| … | <add the "impossible" ones you keep wanting to skip> | | open | | |

> For each: write the **cheapest test that would prove it impossible**, run the most
> **bisecting** one first (`git bisect`, layer-halving, toggle-halving, input
> minimization), and fill the evidence column. Strike off ONLY on evidence.

## 3. Converge

- **Survivors (status = SURVIVING):** <list>
- **If >1:** the discriminating experiment (one the survivors predict *differently*): <describe + result>
- **If exactly 1 — convict the survivor:**
  - Survivor: <the improbable truth>
  - **Confirm — toggle:** <made symptom appear/disappear by manipulating only this cause: result>
  - **Confirm — mechanism:** <how it produces the exact facts, incl. the negative ones>
  - **Fix:** <the change>
  - **Verify (paste the real artifact):** <e.g. "stale_rate 0/100k, zero old SHAs" — not "should be fixed">
- **If 0 survivors — the method failed, not the universe:**
  - Which alibi was an *assumption* not *evidence*? → re-test: <which>
  - Which improbable cause did I never list? → add: <which>

## 4. Case notes / ledger

- <append each test run: suspect → test → result (eliminated? / survived?), newest first>
