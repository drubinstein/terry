# Metrics & Hotspot Analysis — making a system tell you the truth

The OBSERVE and ANALYZE steps are only as good as the signal you feed them. This
doc is the how-to for two things: (1) making a system **observable** through a
structured channel instead of a buffered log, and (2) turning a raw run into
**root-cause facts** — the hotspot/sink, the oscillation, the spike, the final
state — mechanically, so the next action is data-driven and not eyeballed.

The mantra: **measure first, then act.** You cannot optimize, fix, or steer what
you cannot observe — and a log grep is not observing.

```
   run/system  ──(structured channel)──►  raw signal  ──(analyzer)──►  facts
   ┌─────────┐    /state endpoint (JSON)   ┌────────┐   parse + rank   ┌──────────┐
   │  LIVE   │    --metrics counter stream │ visits │   most-visited   │ HOTSPOT  │
   │ SYSTEM  │    traces / spans           │ bounces│   top A↔B        │ BOUNCE   │
   └─────────┘    a runtime probe          │ deltas │   per-window     │ SPIKE    │
                                           │ final  │   end-state      │ FINAL    │
                                           └────────┘                  └──────────┘
```

---

## 1. Structured polling over log-grep

A buffered log file is the worst signal: it lags (buffering), it's unparsed
(regex archaeology), and it's noisy (everything is in there). Replace it with a
channel built for querying.

### 1a. A live status endpoint (poll the present)

Expose current state on a tiny HTTP/IPC endpoint and poll THAT for "where is it
now?":

```bash
# Unbuffered, parseable, exact — the present state in one call:
curl -s --max-time 5 http://127.0.0.1:${PORT}/state | python3 -m json.tool
# → { "phase": "...", "progress": 0.62, "metric": 0.48, "alive": true, ... }
```

Drive ALL active runs each cycle by polling each one's endpoint — don't let one
run starve because you only watched another's log.

### 1b. A machine-readable metric/event stream (record the past)

Have the run EMIT counters/events on purpose, in a grep-stable format, so an
analyzer can reconstruct what happened:

```bash
<your-run> --metrics > run.log 2>&1
# emits lines like:
#   metric_visits   <node> <count>
#   metric_bounce   <a><->><b> <count>
#   metric_delta    t=<tick> <node> <delta>
#   FINAL <scalar> <position> <flags>
```

ALWAYS launch validation/iteration runs with the metric stream on, so the NEXT
iteration's analyzer has data. A run you can't analyze is a wasted cycle.

### 1c. Three pillars

Metrics (what/how-much), logs (discrete events), traces (causal spans). For the
loop you usually need: a scalar METRIC to gate on, a structured EVENT/visit
stream to find the hotspot, and — for "why is this slow/stuck" — a TRACE/span to
find the longest path. Pick the cheapest pillar that answers the current
question.

---

## 2. Turn signal into facts (the analyzer)

Don't eyeball a 50k-line log. Run a mechanical analyzer that ranks the signal
into the four facts that pick the next action. (Skeleton:
`templates/analyze-metrics.py` — adapt the parse patterns to your stream.)

### 2a. Hotspot / sink — where it's stuck or spending time

The most-visited node (or longest-duration span, or highest-failure step). A node
visited far more than its neighbors is a SINK: the loop keeps returning there
because it's stuck retrying. In perf terms, the hottest frame in the flamegraph.

```
Top visits:
  node_C   412     ◄── SINK: 4× the next node; the loop is stuck here
  node_A    98
  node_B    91
```

### 2b. Oscillation / bounce — burning iterations without progress

The highest back-and-forth A↔B transition count. A loop flipping between two
states is making no net progress — a retreat-then-re-enter, a retry that
un-does itself, a pass↔fail flip correlated with order.

```
Top bounces (oscillation):
  node_C <-> node_B   57     ◄── flip-flopping; no forward progress
```

### 2c. Spike — WHEN, not just how-much

Group deltas by a time/iteration window; the biggest per-window delta tells you
the PHASE in which a node got hammered, not just its lifetime total. Distinguishes
"slow start, fine after" from "degrades over time."

```
Spikes (delta >= threshold per window):
  t=1.2M   node_C   delta=31    ◄── hammered late → progressive degradation
```

### 2d. Final state — the metric + where it ended

The scalar metric value, the end position, the flags. This is what the
keep-or-revert gate reads, and what VERIFY-BEFORE-CLAIM pastes as evidence.

### 2e. Domain heuristics on top

Once the four facts are mechanical, encode a domain rule that flags a known
pattern, e.g. "any retry-only node with visits > 3 ⇒ a retry loop wasting time".
Keep these as cheap hints layered ON the facts, not as the facts themselves.

---

## 3. The signal/metric/budget mapping across domains

The loop is domain-agnostic because every domain has the same three slots. Fill
them in for your problem:

| Domain | SIGNAL (observe) | SCALAR METRIC (gate) | FIXED BUDGET (per trial) |
|---|---|---|---|
| CI / test triage | test/job report (JUnit/JSON) | # failing tests | one pipeline run |
| Perf tuning | flamegraph / latency histogram / trace | p99 latency | one fixed benchmark |
| Flaky-test hunt | pass/fail over N reruns | failure rate over N | K reruns at a fixed seed |
| Hyperparameter search | val-loss curve | val loss | fixed train minutes/steps |
| Long autonomous run | live `/state` endpoint, metric stream | checkpoint/progress reached | fixed step/tick cap |
| Incident response | dashboards, traces, error rate | error rate / SLO burn | one bounded canary/probe |

Keep-or-revert is `git commit` vs `git revert` in every row. If a domain has no
natural scalar metric, you must MANUFACTURE one (e.g. "% of N runs that reach
checkpoint") before the loop can run — a metric is non-negotiable.

---

## 4. Empirical probe over static analysis (ground truth)

For facts about the RUNNING system, a static model is a hint; the live system is
ground truth.

- **Runtime probe** — load a known state, take one action, read the result. This
  is what the system actually does. Use it for go/no-go decisions on the critical
  path.
- **Static model** — a decoded data file, a unioned/merged table, a simulator
  with idealized inputs, a tool's "unreachable/impossible/nonviable" verdict.
  Useful for cheap pre-screening, WRONG often enough that you must confirm before
  pruning a branch on it.
- **Disagreement is the clue.** When static says one thing and the live run says
  another, the model is wrong about THIS case — investigate the model, don't
  override the system. A model false-negative that prunes a viable
  critical-path branch is expensive; spend one cheap real run to confirm any
  blocking "impossible".

Staged promotion: screen cheaply with the static model, but PROMOTE only what a
runtime probe confirms. (See `lessons-and-antipatterns.md` §3 for the full
Symptom→Root cause→Fix.)

---

## 5. Observability checklist (do this BEFORE the first iteration)

- [ ] A structured live channel exists (a `/state` endpoint or equivalent) —
      not just a log file.
- [ ] The run emits a machine-readable metric/event stream (`--metrics` or
      equivalent), ON for every iteration run.
- [ ] A scalar METRIC is defined, cheap to read, monotone toward the goal.
- [ ] An analyzer ranks the stream into hotspot / bounce / spike / final state
      (adapt `templates/analyze-metrics.py`).
- [ ] For any "impossible/unreachable" verdict on the critical path, a runtime
      probe is run to confirm before pruning.
- [ ] You poll EVERY active run each cycle, not just the one you're focused on.

## 6. Quick triage table (observation → look here)

| You see… | Likely fact | Where |
|---|---|---|
| One node visited far more than the rest | Sink — stuck retrying | §2a |
| Two nodes flip back and forth | Oscillation — no net progress | §2b |
| Totals look fine but it degrades over a run | Spike — phase-specific | §2c |
| You're grepping a log for status | Missing structured channel | §1 |
| A tool says "impossible" but it works live | Model false-negative | §4 |
| No number decides keep-vs-revert | Missing scalar metric | §3 |
