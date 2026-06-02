# Why you strike off the true cause — biases & false eliminations

Sherlock fails in exactly one way: **you eliminate the real cause on an assumption
instead of on evidence.** Every entry below is a flavor of that single mistake.
Violating the letter of "eliminate only by proof" is violating the spirit of the
method — there are no exceptions for causes that are "obviously" innocent.

## The biases that forge alibis

| Bias | Sounds like | The fix |
|------|-------------|---------|
| **Incredulity** ("that's impossible") | "It can't be the cache, we invalidate on write." | Impossibility is a *hypothesis to test*, not a verdict. Run the cheap decisive test anyway. |
| **Confirmation** | "Let me add logging to prove it's the DB." (then reading everything as DB) | Design the test to **kill** your theory, not confirm it. Predict what you'd see if you're *wrong*. |
| **Anchoring** | "It's probably the thing I first suspected." | First theories are guesses made with the least data. Re-rank only by evidence, not by order. |
| **Recency / "blame the last change"** | "It broke after my deploy, so it's my deploy." | Often right — but *prove* it (`git bisect`, revert-and-retest). Correlation in time is a lead, not an alibi for everything else. |
| **Authority / "it's well-tested"** | "It's the stdlib / the compiler / Postgres — those don't have bugs." | Reputation is not evidence. Usually it's *your misuse* of the trusted thing — but you still test it, you don't assume it. |
| **Ego protection** | "It surely isn't *my* code." | Follow facts docilely wherever they lead, including to your own recent diff. |
| **Sunk cost** | "I've spent an hour on the race-condition theory, it must be that." | Time spent is not evidence. A theory with no decisive test behind it is still open. |
| **Streetlight** | "I only know how to check X, so it's probably X." | Enumerate the *complete* list first, then pick tests — not the reverse. |

## The "impossible" culprits that are actually possible

When you're stuck with an empty board, the truth is usually one of these — the
suspects everyone strikes off by reputation:

- **"The compiler is wrong."** Almost always **your undefined behavior** (UB),
  optimization exposing an aliasing/uninitialized bug, or a flag/version mismatch.
  Rare, but real compiler bugs exist — test with `-O0`, a different version, or
  sanitizers (ASan/UBSan/TSan) before *or instead of* blaming or absolving it.
- **"The standard library / framework is broken."** Almost always **your misuse**
  (wrong contract, a non-thread-safe call from two threads, an iterator
  invalidation). Read the contract; write the minimal repro against the library.
- **"It's decommissioned / not deployed / not running."** Zombie process, stale
  container, an old instance still in the LB pool, a cached artifact, a second copy
  on a forgotten host. **Stamp identity** (build-SHA, PID, hostname) and check.
- **"The clocks are synced."** Clock skew, NTP step, DST, timezone, leap second,
  monotonic-vs-wall confusion. Cheap to measure — measure it.
- **"Caching can't be it."** App cache, Redis, CDN/edge, browser, DNS TTL, an ORM
  identity map, a memoized value, the build cache. Bypass each directly and compare.
- **"It's not a race, it's deterministic."** Then it reproduces identically every
  time — *prove* that with two byte-identical runs. If it doesn't, it has a
  nondeterministic cause (timing, ordering, uninitialized memory, hash-seed,
  iteration order); it is **not** "flaky."
- **"The hardware is fine."** A single bad node/disk/NIC, ECC-corrected (or
  uncorrected) memory, thermal throttling. Rare — but if the symptom is localized to
  one machine, *test the machine* (move the workload; swap the node).
- **"The test is correct, the code is wrong."** Sometimes the **observer** is the
  bug: a flaky fixture, an order-dependent test, a wrong assertion, the repro script
  itself, logging that changes timing. Suspect the measurement, especially for
  Heisenbugs that vanish under instrumentation.
- **"A uniqueness / idempotency guard makes duplicates impossible."** A constraint
  protects the *row*, not the *side effect taken before the row commits*. Under
  concurrency two checks can both pass (TOCTOU) and each fire an irreversible action
  (a charge, an email, a webhook) **before** either insert commits — the guard then
  rejects the second *row*, but the second *action already happened*. Or the guard
  is on the wrong column/scope, or a retry layer mints a fresh key so it never sees
  two equal values. **Test:** read the two persisted records' keys byte-for-byte
  (same ⇒ guard fired late / wrong column; different ⇒ a layer minted a new key),
  and replay two concurrent operations to see if both side-effect before either
  commits.
- **"Each test is isolated."** Pass-alone / fail-in-suite (even with fixed order) is
  the fingerprint of **inter-test state leakage**, not a framework bug: a
  module-level singleton/cache/registry, an env var or monkeypatch left set, a
  session/module-scoped fixture mutated by an earlier test, a leaked
  thread/connection, or hash/iteration order seeded by a prior test. **Test:**
  bisect the suite to find the poisoning predecessor and stamp global state
  before/after it.

## Red flags — STOP, you're eliminating by assumption

If you catch yourself thinking any of these, you are about to forge an alibi:

- "That **can't** be it." → It can. Test it.
- "It's **surely** not the library/compiler/OS/hardware." → Reputation ≠ evidence.
- "We **decommissioned/disabled** that." → Verify with an identity stamp.
- "I'll add logging to **confirm** my theory." → Try to falsify it instead.
- "It **must** be the last change." → Bisect and prove it; don't absolve everything else.
- "Nothing is left, this bug is **impossible**." → You over-eliminated or
  under-enumerated. The method is telling you *you* erred.
- "Two suspects left; I'll just **fix the likely one**." → Run the discriminating
  test first; a guessed fix re-opens the case and corrupts the board.

**All of these mean: put the suspect back on the board and design a falsifying
test.**

## Rationalization table

| Rationalization | Reality |
|-----------------|---------|
| "Listing the impossible causes is a waste of time." | The impossible cause is where the truth usually is — that's the maxim. Listing is cheap; a missing suspect costs hours. |
| "I'm confident enough to skip the test." | Confidence is the feeling that precedes most false eliminations. The test is cheap; being wrong isn't. |
| "Probability says it's X, so I'll fix X." | Probability ranks *which test to run first*, never *which suspect to convict without one*. |
| "The survivor is too improbable to be real." | After correct elimination, improbable is all that *can* remain. Confirm it; don't reject it for feeling unlikely. |
| "Nothing's left, so the tools/environment must be cursed." | 'Cursed' = an un-listed or wrongly-eliminated cause. Re-examine your most confident alibi. |
| "Reproducing it once is enough to know the cause." | Reproduction locates the symptom, not the cause. The cause is what survives elimination and confirms on toggle. |
