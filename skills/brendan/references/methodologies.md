# The rest of the toolkit — methods beyond USE (and anti-methods to avoid)

The USE method is the fast resource sweep. These are the complementary
methodologies from Brendan Gregg's *Systems Performance* — reach for the one whose
**question** matches yours. Most investigations chain them: USE to find the hot
resource → drill-down/latency/off-CPU to localize → flame graph to see the code.

## Pick the method by question

| Your question | Method |
|---------------|--------|
| "Which *resource* is the bottleneck?" | **USE** (resource sweep) |
| "Where does *this thread/process* spend its time?" | **TSA** (thread-state) |
| "*Who/what* is generating the load, and is it expected?" | **Workload characterization** |
| "The load is real — *where in the stack* does the time go?" | **Drill-down analysis** |
| "*Why* is this request slow?" (the long tail) | **Latency analysis** |
| "Resources all look unsaturated, but p99 is still bad" | **Off-CPU + Latency analysis** |
| "It's blocked, not busy — *what is it waiting on*?" | **Off-CPU analysis** |
| "*Which code paths* burn the CPU?" | **CPU flame graph** |
| "How healthy is this *service/endpoint*?" | **RED method** |

## TSA — Thread State Analysis

Thread-oriented counterpart to USE. Every thread is, at any instant, in exactly
one of six states; the method is two steps:

1. **For each thread of interest, measure total time in each state.**
2. **Investigate states from most-time to least, with the right tool.**

| State | Meaning | Where to look next |
|-------|---------|--------------------|
| **Executing** | on-CPU (user/sys) | CPU flame graph — which code? |
| **Runnable** | waiting for a CPU | CPU saturation (USE: run-queue) — add CPU / reduce demand |
| **Anonymous paging** | blocked on memory residency | memory saturation (swapping) |
| **Sleeping** | waiting on I/O (disk, net, page-in) | off-CPU analysis — which resource? |
| **Lock** | waiting to acquire a lock | lock contention (off-CPU / `lock_stat`) |
| **Idle** | waiting for work | usually fine — not a bottleneck |

A thread that is mostly **Runnable** is CPU-starved; mostly **Sleeping** is
I/O-bound; mostly **Lock** is contention-bound. TSA tells you *which* USE resource
to chase from the thread's point of view. Tools: scheduler tracing, `/proc/<PID>/
schedstat`, delay accounting, `offcputime`/`wakeuptime` (bcc), `bpftrace`.

## Workload characterization

Don't analyze the machine — analyze the **demand**. Answer four questions about
the load *before* tuning, to find load that simply shouldn't exist (the biggest
wins are often "stop doing this," not "do it faster"):

1. **Who** is causing the load? (PID, user, IP, tenant)
2. **Why** is it being called? (code path, stack, call reason)
3. **What** is the load? (IOPS, throughput, direction, type — read/write)
4. **How** is it changing over time? (trend, burstiness)

## Drill-down analysis

Peel the stack layer by layer, moving the investigation **down** toward the
source. Three stages: **Monitoring** (system-wide, ongoing) → **Identification**
(narrow to a subsystem/resource) → **Analysis** (examine that piece in depth).
E.g. slow request → app frame → syscall → filesystem → block device → disk; at
each layer pick the metric that points to the next layer down.

## Latency analysis

Target the **time** a request spends, not resource counters. Start at the highest
level (request latency), then **decompose** it into synchronous components,
attributing time to each (e.g. total = queueing + service; service = CPU + disk +
lock-wait). Repeat on the dominant component. This is the method for **tail
latency** and SLO work where USE (which looks at saturation, not per-request time)
comes up empty. Tools: distributed tracing, `funclatency`/`biolatency` (bcc),
USDT/uprobes, latency histograms. When the decomposed time lands in a **blocked
(off-CPU)** component and no resource is saturated, continue with **Off-CPU
analysis** (below) — that's the pair for "unsaturated but slow."

## Off-CPU analysis

The counterpart to on-CPU profiling: profile threads **while they are blocked**
(off-CPU), and capture the stack + the duration of each blocking event. Answers
"what is it *waiting* on?" — disk, network, locks, scheduler. An **off-CPU flame
graph** (`offcputime -df` → flamegraph) visualizes blocked time the way a CPU
flame graph visualizes busy time. Essential when USE shows low utilization but the
app is still slow (it's blocked, not busy).

## Flame graphs

Visualization, not a method per se, but the payoff of on/off-CPU profiling.
Sampled stacks are merged into a hierarchy: **x-axis = population (not time)**,
**y-axis = stack depth**; width = how often a frame was present in samples. Read
**plateaus** (wide frames) as the hot paths. Variants: **CPU** flame graph
(on-CPU, from `perf record -F 99 -ag` or `profile`), **off-CPU** (blocked time),
**memory/alloc**, **differential** (before/after a change — colored by delta).

```bash
perf record -F 99 -a -g -- sleep 30
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > cpu.svg
# modern: profile -F 99 30 > out.folded ; flamegraph.pl out.folded > cpu.svg   (bcc)
```

## RED method (services — Tom Wilkie)

For **request-driven services** (the complement of USE's resources), monitor three
signals per service/endpoint:

- **Rate** — requests/sec
- **Errors** — failed requests/sec
- **Duration** — latency distribution (p50/p90/p99)

USE is for *resources* (machine-centric); RED is for *services* (request-centric).
Use both on a microservice fleet: RED at the endpoint, USE on the nodes.

## Anti-methods — name them so you stop doing them

| Anti-method | What it looks like | Why it fails |
|-------------|--------------------|--------------|
| **Streetlight** | running the tools you happen to know (`top`, then `top` again) | you only check where the light is, not where the problem is |
| **Drunk-man / random-change** | tweak knobs at random, hope a number moves | unbounded, unrepeatable; "improvements" are noise |
| **Blame-someone-else** | "must be the network/DB" → hand off without evidence | no measurement; bounces the problem around |
| **Ad-hoc checklist** | run a memorized list with no model of *why* | misses anything not on the list; no completeness guarantee |

The cure for all four is the same: start from a **complete resource list** (USE)
or a **decomposed latency budget**, measure before you conclude, and change **one
thing at a time** under a metric (hand off to **`andrej`** for the change loop).
