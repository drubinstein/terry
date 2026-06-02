---
name: sherlock
description: Invoke when a bug resists the obvious explanation and you're stuck — a "this is impossible / can't be happening" heisenbug, an intermittent or nondeterministic failure with many candidate causes, a regression with many possible culprits, a works-here-fails-there environment bug, or the moment you think "I've checked everything and nothing explains it." Root-cause by ELIMINATION: enumerate every possible cause, rule each out with decisive evidence (never assumption), and trust the improbable survivor. Covers the complete-suspect-list, falsify-don't-confirm, the dog-that-didn't-bark (negative evidence), and the "eliminated everything / nothing's left" trap.
---

# Sherlock — root-cause by elimination

> *"When you have eliminated the impossible, whatever remains, however improbable,
> must be the truth."* — Sherlock Holmes, *The Sign of the Four*

Sherlock is the **differential-diagnosis discipline** for bugs. Instead of
chasing your favorite theory, you build the **complete list of possible causes**,
then **eliminate each one with decisive evidence** — never with a hunch or a
reputation — until a single explanation survives. Whatever survives is the truth,
however much it "shouldn't" be possible.

The whole method turns on one asymmetry: **you cannot confirm your way to a root
cause, but you can eliminate your way there.** Confirmation flatters the theory you
already hold; elimination is forced to consider the ones you don't.

Six moves, each a guard against the way bug-hunts actually fail:

- **The complete suspect list.** Enumerate *all* candidate causes up front —
  including the ones you "know" can't be it. An **incomplete list** is the #1
  reason a bug "can't be found": the true cause was never written down.
- **Eliminate by proof, not by reputation.** A suspect leaves the board only when a
  test makes it *impossible*. "The stdlib is well-tested," "we decommissioned that,"
  "the compiler doesn't have bugs" are **not evidence** — they're the exact
  assumptions the real bug hides behind.
- **Falsify, don't confirm.** Design the test that would **kill** your leading
  theory, not the one that flatters it. *Twist theories to fit facts; never twist
  facts to fit theories.*
- **The dog that didn't bark.** The **absence** of an expected signal — a missing
  log line, an error that never fired, a retry that never happened — is evidence.
  *Observe*, don't merely *see*.
- **Trust the improbable survivor.** When one cause remains, accept it even though
  it "can't" happen, then **confirm** it. The bug that can't happen *is* happening.
- **Zero survivors ⇒ your reasoning failed, not the universe.** If you've
  eliminated everything, you either **over-eliminated** (killed a suspect on
  assumption, not proof — re-test it) or **under-enumerated** (the cause is one you
  dismissed as impossible — widen the list). This branch is the maxim itself.

## When to use

Reach for Sherlock when the obvious explanation is gone and you're **choosing among
many candidate causes**:

- a "this is impossible / can't be happening" bug — a heisenbug, or one that
  vanishes under the debugger / with logging added
- intermittent, flaky, or nondeterministic failures with several plausible causes
- a regression where many things could be the culprit (which commit? which layer?
  which dependency bump?)
- works-on-my-machine / fails-in-CI / fails-only-in-prod environment bugs
- the moment you catch yourself saying **"I've checked everything and nothing
  explains it"** — that sentence is the signal to run this method
- two or three theories left and you're tempted to just fix the likely-looking one

## When NOT to use

- The cause is **obvious** — a clear stack trace pointing at one line. Just fix it.
  (But if the "obvious" fix doesn't make the symptom vanish, the cause wasn't
  obvious — open a board.)
- You have **no facts yet** — nothing reproduced, no logs, no trace. *"It is a
  capital mistake to theorise before one has data."* First make it observable and
  reproduce it (instrument-first — see `andrej` / superpowers:systematic-debugging),
  THEN enumerate suspects. (But a *reported* guarantee — "we have a UNIQUE
  constraint," "the logs show one request," "every dashboard is green" — is a claim
  to **verify**, not a fact: green dashboards are not "no facts," and an unverified
  guarantee goes on the board as a *suspect* until you observe it directly.)
- A pure **performance** "why is it slow" with no discrete wrong behavior — that's a
  resource whodunit; run `brendan`'s USE sweep (it *is* elimination, specialized to
  resources). Sherlock is for **correctness** bugs (a slow path that *also* returns
  wrong data is a correctness bug — use Sherlock).
- A feature/design task with no defect to explain.

## The elimination loop

1. **OBSERVE — collect the facts, no theory yet.** Pin the *exact* symptom and
   gather hard evidence: a reproduction, logs, traces, the failing diff, inputs.
   Write down the **negative facts** too — what should have happened and didn't (the
   dog that didn't bark). Resist theorizing until the facts are on the table.
2. **ENUMERATE — the complete suspect list.** List *every* cause that could produce
   these exact facts. Probability is irrelevant here; **deliberately include the
   improbable and the "impossible."** Sweep the layers so the list is complete:
   your code · your config · the inputs/data · build & toolchain · dependencies ·
   runtime/OS · hardware · environment/network · concurrency & timing · state &
   caching · **the observer/test harness itself**.
3. **ELIMINATE — by decisive, falsifying test.** For each suspect, find the
   *cheapest* observation that can prove it **impossible**, and run it. Prefer tests
   that **bisect** the list (kill half at once). Record *how* each suspect was
   eliminated — the evidence, not the argument. **A suspect you cannot yet disprove
   stays on the board.** Never strike one off because "it can't be that."
4. **CONVERGE** — read the board:
   - **More than one left** → design the single most **discriminating** experiment:
     one the surviving suspects *predict differently*. Run it; it eliminates at least
     one. Loop.
   - **Exactly one left** → that is the truth, **however improbable**. *Confirm* it
     (toggle it on/off and watch the symptom follow; fix it and watch it vanish),
     then fix. Verify before you claim.
   - **Zero left** → **stop and distrust your eliminations.** Find the suspect you
     struck off on *assumption* rather than *proof* and re-test it, or add the
     improbable cause you never listed. (E.g. a "deterministic / no shared state"
     alibi is an *assumption* — prove determinism with two byte-identical runs and
     bisect the suite to expose state a prior test leaked.) Nothing-remains means the
     method was misapplied, not that the bug is supernatural.

Full detail (the bisection strategy, what counts as proof, the over-eliminate /
under-enumerate failure modes, discriminating-test design): **`references/elimination-method.md`**.

## Mental model: differential diagnosis on a case board

- **It's a whodunit, and you're building the suspect board** — names pinned up,
  each crossed off only when it has an alibi *backed by evidence*.
- **An alibi is proof of impossibility, not a character reference.** "She's a
  trusted library" is not an alibi. "The stale response carries an old build-SHA"
  is.
- **The remaining suspect is guilty even if they have no motive.** Improbability is
  not innocence. Confirm, then convict.
- **If everyone has an alibi, one alibi is forged** — or the culprit was never on
  the board. Re-examine the alibis; widen the list.

## Worked example: the API that serves stale data "impossibly"

**Symptom:** ~3% of requests return data ~5 minutes stale. "Impossible — we
invalidate the cache on every write, and the old version was decommissioned."

1. **OBSERVE.** Hammer the endpoint; capture response headers per request. **Negative
   fact (dog didn't bark):** the `cache.invalidate` log line is *absent* on the
   stale responses — the invalidation path didn't run for them.
2. **ENUMERATE** (complete, incl. the "impossible"): (a) app in-process cache TTL,
   (b) shared Redis cache stale, (c) CDN/edge cache, (d) DB read-replica lag,
   (e) a **zombie old-version instance** still in the LB pool ("but it's
   decommissioned"), (f) client-side cache, (g) clock skew breaking TTL math ("but
   NTP-synced"), (h) the load test reusing a cached HTTP client.
3. **ELIMINATE by proof** (not by reputation):
   - (c) CDN: stale responses carry `X-Cache: MISS`, `Cache-Control: no-store` → can't be the CDN. ✗
   - (f) client / (h) harness: reproduced with a fresh `curl --no-keepalive` → ✗ both.
   - (d) replica lag: the stale value predates the last write by *minutes*, but replica-lag metric is <1s → ✗.
   - (b) Redis: a direct `GET` of the key returns the *fresh* value with a correct TTL → ✗.
   - (g) skew: host clocks agree within 5 ms → ✗.
   - (e) "decommissioned instance": **do not eliminate on assumption.** Test it — stamp every response with its instance build-SHA. 3% of stale responses carry an **old SHA**.
4. **CONVERGE.** One survivor: (e). However improbable ("it's decommissioned"),
   it's the truth — a half-finished deploy left a zombie instance in the load
   balancer serving old code, and its invalidation path was the old one (hence the
   silent dog). **Confirm:** drain that instance → stale rate drops to 0, no more old
   SHAs. Fix the deploy to deregister it. **VERIFY BEFORE CLAIM:** paste "stale_rate
   0/100k, zero old SHAs," not "should be fixed."

The lesson is the 0-survivor trap dodged: had you struck (e) off on "it's
decommissioned," your board would be empty and you'd be "stuck on an impossible
bug" — when really you'd eliminated the truth on an assumption.

## Quick start

1. **Open a case board** — write the exact symptom and the facts, including the
   *negative* facts (what didn't happen):

   ```bash
   cp skills/sherlock/templates/suspect-board.md suspect-board.md
   ```

2. **Enumerate the COMPLETE suspect list** — sweep every layer (code · config ·
   data · build · deps · runtime · hardware · env · concurrency · state · the
   harness itself) and **include the improbable**. Probability comes later.

3. **For each suspect, write the decisive falsifying test** — the cheapest
   observation that proves it *impossible*. Run the most **bisecting** one first;
   strike a suspect only on **evidence**, and record *how*.

4. **Converge:** >1 left → run the most **discriminating** experiment; exactly 1 →
   **confirm the improbable survivor** and fix; 0 → **un-eliminate the assumption**
   or widen the list. Then verify the fix with the real artifact.

## References

- `references/elimination-method.md` — the loop in depth: building a *complete*
  differential, what counts as proof (eliminate-by-evidence vs eliminate-by-
  assumption), bisecting the suspect set, designing the discriminating experiment,
  and the over-eliminate / under-enumerate branches when nothing remains.
- `references/holmesian-principles.md` — the Holmes canon mapped to debugging,
  operationally: data-before-theory, observe-vs-see, the dog in the night-time
  (negative evidence), reasoning backward, twist-theories-to-facts, and the maxim
  itself — each with the bug-hunt move it licenses.
- `references/biases-and-false-eliminations.md` — why you wrongly strike off the
  true cause (incredulity, confirmation bias, anchoring, recency/"blame the last
  change", authority/"it's well-tested"), the catalogue of "impossible" culprits
  that are actually possible (your UB not the compiler; your misuse not the stdlib;
  the test harness; clock skew; caches; a zombie instance; ECC/cosmic-ray), and the
  rationalization table + red flags.

## Templates

- `templates/suspect-board.md` — a fill-in case board: the symptom + facts (incl.
  negative facts), the complete suspect list across layers, and per suspect a
  status (open / eliminated-by-evidence / **surviving**), the decisive test, and the
  evidence — so the investigation is complete, auditable, and never re-litigates a
  cleared suspect.

## Relationship to systematic-debugging, andrej & brendan

Sherlock is the **elimination lens**, not a replacement for the broader debugging
flow:

- **superpowers:systematic-debugging** is the overall reproduce → isolate →
  root-cause loop. Sherlock is what you run **inside the isolate/root-cause step**
  when many causes are in play and the obvious one is gone. Use systematic-debugging
  for the flow; reach for Sherlock the moment you're *choosing among suspects*.
- **`andrej`** is the observe→analyze→act metric loop: it makes the symptom
  observable (the instrument-first step in *When NOT to use*) and then carries 1–2
  hypotheses, iterating each toward a metric. Sherlock instead enumerates **all**
  hypotheses and kills them. They meet at the discriminating experiment: Sherlock
  decides *which* one-variable test best separates the survivors; `andrej` runs it
  cleanly (fixed budget, keep-or-revert) and logs it. Use Sherlock to pick the
  experiment; `andrej` to execute it.
- **`brendan`** is elimination specialized to **performance** — the USE sweep
  enumerates resources and rules each out. Sherlock is the general-purpose version
  for **correctness** bugs; the shape (complete list → eliminate each → the survivor
  is it) is identical.
