# The Holmes canon, mapped to debugging

Each maxim below is a real debugging move, not a literary flourish. The quote, then
the operational rule it licenses.

## The maxim itself

> *"When you have eliminated the impossible, whatever remains, however improbable,
> must be the truth."* — *The Sign of the Four*

**Move:** enumerate the complete set of causes, eliminate each by evidence, and
**convict the survivor even when it's improbable.** Its contrapositive is the most
useful part: *if nothing remains, you eliminated something you shouldn't have, or
never listed the real cause.* Nothing-remains is a bug in your reasoning, not in
reality. (See `elimination-method.md` step 4.)

## Data before theory

> *"It is a capital mistake to theorise before one has data. Insensibly one begins
> to twist facts to suit theories, instead of theories to suit facts."* — *A
> Scandal in Bohemia*

**Move:** gather a reproduction, logs, and traces **before** forming a favorite
hypothesis. An early theory contaminates every later observation (you'll read
ambiguous evidence as supporting it). When a fact contradicts your theory, **change
the theory** — never explain the fact away.

## Observe, don't merely see

> *"You see, but you do not observe. The distinction is clear."* — *A Scandal in
> Bohemia*

**Move:** read what the evidence *actually says*, not what you expect. The exact
error code, the precise timestamp delta, the byte that differs, which 3% of
requests. Most "impossible" bugs are sitting in plain sight in a log everyone
skimmed. Diff the working vs broken case byte-for-byte; the difference is the clue.

## The dog that didn't bark — negative evidence

> *"the curious incident of the dog in the night-time."* / *"The dog did nothing in
> the night-time."* / *"That was the curious incident."* — *Silver Blaze*

**Move:** the **absence** of an expected signal is evidence. No error logged where
one should be. No cache-invalidation line. A retry that never fired. A callback that
never ran. A metric that stayed flat when it should have moved. Always ask *"what
should be here and isn't?"* — and put each missing signal on the board. Negative
facts often eliminate more suspects than positive ones, because they prove a code
path *didn't execute*. **To find a missing signal** (you can't grep for what isn't
there): diff a known-good trace against the broken one and look for the step present
in the good sequence and absent in the bad — that gap is the dog; or *assert* the
expected signal exists and watch the assertion fail for exactly the affected
entities.

## Reason backward

> *"In solving a problem of this sort, the grand thing is to be able to reason
> backwards… Most people, if you describe a train of events to them, will tell you
> what the result would be… There are few people, however, who… can tell you what
> steps led to that result. This power is what I mean when I talk of reasoning
> backward, or analytically."* — *A Study in Scarlet*

**Move:** start from the **effect** and work toward the cause. Given this exact
wrong output, what is the set of states that could produce it? What is the last
point the data was correct? Walk *upstream* from the symptom along the causal chain
(stack, data flow, request path), asking at each layer "was it already wrong when it
arrived here?" — a binary search backward to the origin.

## Twist theories to facts

> *"I make a point of never having any prejudices, and of following docilely
> wherever fact may lead me."* — *The Reigate Puzzle*

**Move:** hold no favorite. When the evidence points somewhere inconvenient (your
own recent code; a component you trust; a cause you find embarrassing), **follow
it**. The instinct to protect a theory — or a component's reputation — is how the
true cause keeps its alibi.

## Eliminate the improbable last, not first

> *"How often have I said to you that when you have eliminated the impossible…"*

**Move:** improbability is a reason to test a suspect **carefully**, not a reason to
skip it. The probable causes get checked and cleared early by everyone; that's
*why* the survivor is improbable. "Unlikely" earns a cheap decisive test, never an
automatic alibi.

## The composite method (how a Holmes investigation runs)

1. **Observe** the scene exhaustively; note what's present *and* absent.
2. **Enumerate** every party who could have done it — including those with an alibi.
3. **Reason backward** from the effect to constrain who/what could produce it.
4. **Test** each suspect's alibi against *evidence*; a reputation is not an alibi.
5. **Convict** the one who remains, however improbable; then **confirm** the
   mechanism end-to-end before closing the case.
