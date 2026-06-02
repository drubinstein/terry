# The "can't reproduce" playbook

A real bug that won't reproduce for you is a **mismatched condition**, almost never
a false report. This is the catalogue of mismatches, as **Symptom → likely mismatch
→ how to match it**. Work it top-down; the early rows are the most common.

> Golden rule: reproduce against the **version the reporter hit**, with the
> reporter's **data**, on the reporter's **platform**, at the reporter's **scale**.
> Four variables explain the large majority of "works on my machine."

## Version & build

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Works on `main`, reporter still sees it | You're testing a **fixed** version; they're on an old release | `git checkout` their exact tag/commit; reproduce there. If fixed on `main`, find the fixing commit → CONFIRMED + "upgrade/backport". |
| Works in your build, fails in theirs | Stale artifact, different build flags, different lockfile/deps, release vs debug | Rebuild clean from their ref; match the lockfile, compiler/runtime version, optimization flags. |
| "Updated and it came back" | A *regression* in a newer version | Bisect between the last-good and first-bad release (`git bisect`). |

## Configuration & flags

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Works locally, fails for them | Different feature flags, env vars, plan/tier, limits, defaults | Pull their config; flip the flags they have; match quotas/limits. |
| Only some users hit it | A flag/experiment bucket, a per-tenant setting | Reproduce inside that bucket/tenant config. |

## Data & inputs

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Works on your sample, not theirs | Your input is **small/clean**; theirs is large/edge/encoded | Use their file (sanitized) or a faithful synthetic: same size, encoding (BOM/UTF-16/CRLF), nulls, unicode, an outlier/poisoned record. |
| **Wrong value/total** (not a crash) | A specific **edge record** (a discount, fractional qty, tax-exempt or foreign-currency SKU, rounding/locale), not input *size* | Rebuild the reporter's **exact** items, not a "similar" or larger sample; vary one edge field at a time. |
| "**Corrupts**/mangles output" but opens for you | Encoding/format/locale-dependent write path; you checked "it opened," not "bytes intact" | Match their file's exact format/encoding/locale; **diff the output bytewise** against expected — don't just open it. |
| Crashes "sometimes" on import | One bad row/record, not the volume | Bisect the dataset (halve until the offending record remains). |
| Only on old accounts | Data migrated from an older schema/version | Reproduce on a migrated/legacy record, not a freshly-created one. |

## Platform, OS & architecture

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Fails only on their OS/browser/device | Linux/macOS/Windows, x86/ARM, browser/version, mobile/desktop | Reproduce on that exact platform (VM, container, device lab, BrowserStack). |
| Numeric/precision diff | float/endianness/word-size, SIMD, libm version | Match arch + toolchain; try `-O0`. |

## Locale, timezone & clock

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Only some regions / some users | Locale (decimal comma, RTL, collation), encoding | Set `LANG`/locale to theirs; test RTL/unicode input. |
| "Happens at night" / date-off-by-one | Timezone, DST boundary, non-UTC server, near-midnight-UTC date | Set TZ to theirs; pick a date on the DST/UTC boundary. |

## Concurrency, load & scale

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Never repro single-user; fails in prod | A **race** needs contention | Run under parallelism/load; hammer the endpoint; add a stress loop. |
| Only "under heavy use" | Scale threshold (memory, pool exhaustion, queue depth) | Reproduce at the reporter's data volume / request rate, not a toy load. |
| Intermittent, no pattern | Timing/ordering/uninitialized state | Amplify: inject latency, pin an unlucky seed, run 100×; raise `k/N` toward N/N. |

## State, ordering & caching

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Only the **second** time / after specific actions | Leftover state, a specific action ordering | Reproduce the *full* preceding sequence, not just the failing step. |
| Works fresh, fails for them | A warm/poisoned cache (app/CDN/browser), stale session | Match cache state; or bypass to confirm; reproduce with their session/cookies. |

## Network & environment

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Only in prod / their network | Proxy, TLS, DNS, latency, a flaky/slow downstream | Reproduce behind the same proxy/latency; mock the slow downstream; match egress. |
| Times out for them only | Bandwidth/latency/MTU, a regional endpoint | Throttle the network; hit the same region. |

## Permissions & the reporter's specific account

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Only one user / one tenant | Role/permission, that account's exact data/state | Reproduce **as that account** (impersonate in a safe env) with their data shape. |

## The observer & "already fixed"

| Symptom | Likely mismatch | Match it |
|---------|-----------------|----------|
| Vanishes when you add logging / attach a debugger | **Heisenbug** — timing/optimization/uninitialized memory | Don't perturb timing: capture out-of-band (sampling, tracing, core dump), test the optimized build. |
| Can't repro at all on current code | **Already fixed** since the report | Reproduce on the reported version; if green on `main`, it's CONFIRMED-and-fixed — find the commit. |
| You "reproduced" a different failure | You matched the wrong symptom | Re-read expected-vs-actual; confirm the artifact matches *their* exact symptom, not a lookalike. |

---

**If you've worked this list and still can't reproduce:** you have either (a) a
condition you can't yet observe → **ask the reporter the one specific missing
variable**, or (b) a genuinely unreproducible-as-written report → **BUSTED with the
sub-class and evidence** (see `verdict-rubric.md`). Never close "can't reproduce"
without saying which.
