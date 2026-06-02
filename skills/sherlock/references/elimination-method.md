# The elimination method — in depth

The maxim is a *procedure*, not an aphorism:

```
                 ┌─────────────────────────────────────────┐
                 │ 1. OBSERVE the facts (+ negative facts)  │
                 └───────────────────┬─────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────┐
                 │ 2. ENUMERATE the COMPLETE suspect list   │
                 │    (include the improbable & impossible) │
                 └───────────────────┬─────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────┐
                 │ 3. ELIMINATE each by a falsifying test   │
                 │    (proof of impossibility, not a hunch) │
                 └───────────────────┬─────────────────────┘
                                     ▼
                          how many survive?
              ┌──────────────┬───────────────┬──────────────┐
              ▼              ▼               ▼
          >1 left        exactly 1         0 left
        discriminating   CONFIRM the     you over-eliminated
        experiment →     improbable      (re-test an assumption)
        loop to 3        survivor, fix   OR under-enumerated
                                          (add the improbable) → loop
```

## 1. Observe — facts before theory

*"It is a capital mistake to theorise before one has data; insensibly one begins to
twist facts to suit theories, instead of theories to suit facts."*

- Nail the **exact** symptom: not "it's flaky" but "request returns HTTP 200 with a
  body field `ts` ~300s behind, on ~3% of calls, only since Tuesday."
- Collect **hard evidence**: a reproduction (ideally a one-command repro), logs,
  traces, the failing diff, the precise inputs, the environment.
- Record the **negative facts** explicitly — see *the dog that didn't bark* below.
  A list of "what should be here and isn't" is half your eliminations already.
- Do **not** form a favorite theory yet. The cost of an early theory is that every
  subsequent observation gets bent to support it (confirmation bias).

## 2. Enumerate — the complete suspect list

The single highest-leverage step. **A bug you "can't find" is almost always a
suspect you never listed.** Probability is *irrelevant* here — you are building the
universe of causes, not ranking them. Deliberately write down the ones you "know"
are impossible; those are exactly where the truth hides.

Sweep these layers so the list is provably complete:

| Layer | Examples of suspects |
|-------|----------------------|
| **Your code** | logic error, off-by-one, wrong branch, race in *your* code |
| **Your config** | flag/env var, feature toggle, wrong endpoint, limits |
| **Inputs / data** | malformed/edge-case input, encoding, a poisoned record, empty set |
| **Build / toolchain** | stale build, wrong artifact, compiler flag/version, codegen |
| **Dependencies** | a lib's behavior/bug, a version bump, transitive dep, ABI mismatch |
| **Runtime / OS** | GC, signal, ulimit, OOM-killer, scheduler, container limit |
| **Hardware** | ECC/memory, disk error, NIC, a single bad node, thermal throttle |
| **Environment / network** | DNS, proxy, LB routing, TLS, clock skew, region, CDN |
| **Concurrency / timing** | race, deadlock, ordering, retry storm, TOCTOU (two checks pass before either commits — a guard protects the row, not the side effect already fired), double-submit/retry minting a new id, async leak |
| **State / caching** | stale cache (app/Redis/CDN/client), replica lag, leftover state |
| **The observer itself** | the test harness, the logging, the debugger, the repro script |

That last row is the Heisenbug's home: a bug that **disappears when you add logging
or attach a debugger** points at timing, optimization, or uninitialized memory —
and sometimes the "bug" is in the *measurement*, not the system.

## 3. Eliminate — proof, not reputation

A suspect is removed **only** when an observation makes it *impossible*. The bar is
evidence, and the test should be **falsifying**: designed to kill the suspect, not
to flatter it.

**Eliminate-by-evidence vs eliminate-by-assumption** — the central distinction:

| Eliminate by EVIDENCE (allowed) | Eliminate by ASSUMPTION (forbidden) |
|---------------------------------|-------------------------------------|
| "Direct `GET` returns the fresh value → not the Redis cache." | "Redis is reliable, it's not that." |
| "Responses carry `X-Cache: MISS` → not the CDN." | "The CDN team would've noticed." |
| "Build-SHA stamp shows old code → it IS the old instance." | "We decommissioned that, so not it." |
| "Disabling the flag makes the symptom vanish → it's the flag." | "That flag is unrelated." |

Every time you want to strike a suspect off, ask: *what is the evidence that makes
this impossible?* If the answer is a reputation, a "should," or a "surely," it
stays on the board.

**Bisect to eliminate in bulk.** Don't test suspects one by one if a single
observation can split the list. Classic bisections:

- **`git bisect`** — which commit introduced it (kills "code" candidates by half).
- **Layer halving** — does it reproduce against the API directly (skip the client)?
  In a fresh container (skip host state)? With one instance (skip LB/routing)?
- **Toggle halving** — disable a whole subsystem; symptom persists ⇒ that whole
  subsystem is innocent.
- **Minimization** — shrink the input/repro until it's minimal; every removed piece
  that doesn't change the symptom eliminates a swath of suspects.

Record *how* each suspect died (the evidence line). The board must be auditable —
you will be tempted to re-litigate a cleared suspect when the survivor feels wrong;
the recorded alibi stops you.

## 4. Converge — read the board

**More than one survivor → the discriminating experiment.** Find the test the
remaining suspects *predict differently*, so one result rules out at least one.
Good discriminating tests have **high information gain**: they split the survivors,
ideally in half. (This is exactly an `andrej` bounded experiment — one variable, a
decisive readout — chosen for maximum elimination.)

**Exactly one survivor → convict, however improbable.** Improbability is not
innocence. But "remaining" is not the same as "confirmed" — *confirm* it:

- **Toggle:** make the symptom appear and disappear by manipulating only that cause.
- **Mechanism:** explain *how* it produces the exact facts, including the negative
  ones (why the dog didn't bark).
- **Fix-and-verify:** fix it, reproduce the original repro, watch the symptom
  vanish, and paste the real artifact (counts/hashes/exit code) — *verify before
  claim*.

**Zero survivors → the maxim's contrapositive.** "Whatever remains must be the
truth" implies: *if nothing remains, you erred.* Two repairs, in order:

1. **Over-elimination (most common).** You struck a suspect off on assumption, not
   proof. Re-read each alibi: which one is a "should/surely/trusted" rather than an
   evidence line? Re-test that one — the truth is usually hiding behind the alibi
   you were most confident in.
2. **Under-enumeration.** The cause was never on the list because you "knew" it was
   impossible. Widen the list: add the improbable layer (hardware? clock? the
   harness? a zombie process? a second writer you forgot exists?). Re-run from
   step 3.

Never conclude "this bug is impossible / unfixable." That conclusion is the method
reporting *its own* failure, not the system's.

## A note on the improbable

The reason the survivor is so often improbable is **selection**: the probable
causes are the first ones everyone checks and rules out, so by the time you're
stuck, only improbable suspects can remain. "However improbable" isn't mysticism —
it's what's left after the obvious has been correctly eliminated. Trust it; confirm
it; fix it.
