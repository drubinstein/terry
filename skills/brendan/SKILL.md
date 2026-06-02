---
name: brendan
description: Invoke when a system is slow, saturated, regressed, or near capacity and you are tempted to guess the bottleneck or reach for a random tool — Brendan Gregg's systems-performance methodology. Covers the USE method (check utilization, saturation, errors for EVERY resource), the 60-second triage checklist, TSA / thread-state, workload-characterization / drill-down / latency methods, the per-resource Linux tool checklist (vmstat, mpstat, iostat, sar, pidstat, perf, bpftrace/bcc), and GPU performance counters (nvidia-smi, dmon/pmon, DCGM, XID/ECC/NVLink, Nsight). Use for capacity, latency, throughput, "where is the bottleneck", and CPU/memory/disk/network/GPU questions.
---

# Brendan — systems-performance methodology (the USE method & friends)

Brendan is the **measure-don't-guess discipline** you run when a system is slow,
saturated, or near capacity. It is Brendan Gregg's body of performance
methodology — most of all the **USE method** — distilled into a skill: instead of
reaching for whatever tool you remember (the *streetlight anti-method*) or blaming
the component you touched last, you walk a **complete list of resources** and, for
each, check three things — **Utilization, Saturation, Errors** — until the
bottleneck names itself.

> **USE in one line:** *For every resource, check utilization, saturation, and
> errors.* It finds ~80% of server issues with ~5% of the effort.

It is the generalization of three metric types applied to every resource:

- **Utilization** — the average time the resource was busy servicing work, as a
  percent over an interval. (Caveat: a 5-min average of 20% can hide 100% bursts.)
- **Saturation** — the degree of *extra* work the resource can't service, usually
  queued. **Any non-zero saturation is a problem.**
- **Errors** — the count of error events. Check these **first**: they're quick to
  read and easy to interpret.

…and the spine that makes it a *method*: a **complete resource list** you refuse
to leave gaps in — CPUs, memory capacity, network interfaces, storage device I/O,
storage capacity, storage/network controllers, and the CPU/memory/I/O
interconnects — each crossed off only when U, S, and E are all accounted for.

## When to use

Use Brendan whenever you face a **resource-bottleneck or capacity question** and
want a systematic sweep instead of a hunch. Typical shapes:

- "the box/app/cluster is slow" with no obvious cause — run the sweep
- a latency or throughput **regression** you need to localize to a resource
- **capacity planning** / "are we near a limit?" / headroom questions
- a saturation symptom (rising queues, tail latency, page-ins, packet drops)
- **GPU** under-utilization or stalls in an ML/HPC job — note `nvidia-smi`
  "GPU-Util" = *any kernel running*, not SM occupancy, so 100% can still be
  **starved**; check true SM activity (`dmon` `sm%` / DCGM `SM_ACTIVE`)
- the first 60 seconds on an unfamiliar Linux host (the triage checklist)
- before you reach for `perf`/flamegraphs — USE first tells you *which* resource
  is worth profiling

## When NOT to use

- A pure **logic bug** with no resource symptom — that's debugging, not perf.
- You already KNOW the bottleneck and just need to fix it — skip the sweep.
- Tuning a **cache** hit-rate in isolation: caches improve under high utilization,
  so they don't fit USE; rule out the systemic resources first, *then* look at
  cache hit ratios.
- A problem that is fundamentally about **latency distribution** of one request
  path rather than a saturated resource — reach for **latency analysis**
  (decompose the request's time budget) or **off-CPU analysis** (an off-CPU flame
  graph shows what it's *waiting* on when nothing is saturated); drill-down /
  flame graphs in `references/methodologies.md`, not the USE sweep.

## The USE procedure (the loop)

Walk the resource list; for each resource, in this order:

1. **ERRORS first** — easiest to interpret, and a hot resource with errors is
   worth investigating regardless of load. Non-zero / increasing error counters
   (including *recoverable* errors and degraded-but-redundant components) → flag.
2. **UTILIZATION** — is it busy? 100% is a *candidate* bottleneck — confirm with
   saturation before concluding (a device with internal parallelism, e.g. NVMe,
   can read 100% util yet not be saturated); sustained >70% can already cause
   queueing delay. Remember averages hide bursts.
3. **SATURATION** — is work queued/waiting it can't service? Any non-zero value
   warrants a look (run-queue length, paging, `avgqu-sz`, drops, retransmits).
4. **Interpret & iterate** — a resource that's hot *and* saturated (or erroring)
   is your suspect. Cross it off only when all three are accounted for; move to
   the next resource. Don't stop at the first 100% — finish the list so you don't
   mistake a symptom for the cause.

Before measuring, sketch a **functional block diagram** of the system (CPUs →
memory → I/O → controllers → devices, annotated with max bandwidths): it makes the
resource list complete and exposes **interconnects** people forget. Then apply the
same U/S/E lens to **software resources** (mutex locks, thread/worker pools,
process/task capacity, file descriptors) and, in the cloud, to **imposed limits**
(instance/cgroup CPU, memory, net, I/O caps — a tenant can saturate a soft limit
while the physical host looks idle).

Full theory (the strategy flowchart, interpretation thresholds, functional
diagram, software & cloud resources, caveats): **`references/use-method.md`**.

## The 60-second triage checklist

On an unfamiliar Linux host, run these ten in order — each peels a different
layer (load → errors → CPU → memory → disk → network → processes):

```bash
uptime                  # load averages — trend over 1/5/15 min: rising?
dmesg | tail            # recent kernel errors: OOM kills, TCP drops, driver faults
vmstat 1                # r (runq > nCPU = CPU saturation), si/so (swapping), us/sy/id/wa
mpstat -P ALL 1         # per-CPU balance — one hot CPU hides in the average
pidstat 1               # per-process CPU, rolling — who is on-CPU right now
iostat -xz 1            # disks: %util, avgqu-sz, await, r/s+w/s — saturation & latency
free -m                 # memory: available vs used; buff/cache; is free truly low?
sar -n DEV 1            # NIC throughput rxkB/txkB vs known link max → net utilization
sar -n TCP,ETCP 1       # TCP active/passive conn rate, retransmits (saturation/errors)
top                     # overall sanity check: top consumers, state
```

This is the fast on-ramp to a full USE sweep; the per-resource commands and what
each field means are in **`references/linux-checklist.md`**.

## Mental model: a coroner's checklist, not a hunch

- **Resource-complete, not tool-first.** Start from the list of *resources*, then
  pick the tool that measures each — the opposite of "I know `top`, let me run
  `top`." Missing-tool gaps become *known* gaps, not silent ones.
- **Errors → Utilization → Saturation, per resource.** A fixed, boring order so
  you never skip the cheap signal.
- **The bottleneck is the saturated resource, not the busy one.** 100% util with
  zero queue may be fine; 60% util with a growing queue is the problem.
- **USE is resource-oriented; TSA is thread-oriented.** When the suspect is "my
  process is slow" rather than "a resource is hot," flip to **Thread State
  Analysis** — measure where each thread spends time (Executing, Runnable,
  Anon-paging, Sleeping/I-O, Lock, Idle) and attack the biggest slice. The two are
  complementary (`references/methodologies.md`).

## Worked example: "the service got slow after deploy"

1. **60-second triage.** `uptime` shows load 30 on 8 CPUs (high). `vmstat 1`:
   `r`=24 (run-queue ≫ 8 → **CPU saturation**), `si/so`=0 (not swapping), `wa`
   low (not disk-bound). `dmesg | tail` is clean (no errors).
2. **USE sweep, CPU resource.** Errors: `perf`/MCE clean. Utilization:
   `mpstat -P ALL 1` → all 8 CPUs ~95% in `%usr` (not `%sys`, not `%iowait`) —
   genuinely compute-bound, evenly balanced. Saturation: `vmstat` `r` confirms a
   deep run-queue; `sar -q` runq-sz agrees. **CPU is the bottleneck** (hot *and*
   saturated, in user time).
3. **Cross off the rest so you don't fix a symptom.** Memory `free -m`: ample
   available, `vmstat` paging zero — not memory. Disk `iostat -xz 1`: `%util` low,
   `avgqu-sz`<1 — not disk. Net `sar -n DEV/TCP`: throughput modest, retransmits
   ~0 — not network. List is clean except CPU-user.
4. **Now—and only now—profile the hot resource.** A CPU **flame graph**
   (`perf record -F 99 -ag -- sleep 30` → flamegraph, or `profile -F 99`) shows
   the new deploy's JSON serializer dominating on-CPU time. That's the cause; USE
   pointed the profiler at the right resource instead of guessing.

VERIFY BEFORE CLAIM: report the actual numbers (`r`=24/8 CPUs, `%usr`=95, the
flame-graph frame %), not "seems CPU-bound."

## Quick start

1. **Triage in 60 seconds** to localize the layer:

   ```bash
   bash skills/brendan/templates/60s-triage.sh     # runs the ten checks, annotated
   ```

2. **Open a USE worksheet** and walk the resource list — one row per resource,
   filling U / S / E so gaps are visible:

   ```bash
   cp skills/brendan/templates/use-worksheet.md use-worksheet.md
   # for each resource: record the U/S/E metric, its value, and a verdict
   ```

3. **Look up the exact command** for any (resource × U/S/E) cell in the Linux
   checklist; for a GPU job use the GPU checklist (`nvidia-smi`, DCGM, XID/NVLink):

   ```bash
   # references/linux-checklist.md  — CPU/mem/net/disk/controllers/interconnects + software resources
   # references/gpu-checklist.md    — nvidia-smi dmon/pmon, DCGM dcgmi/dcgm-exporter, XID/ECC/NVLink, Nsight; ROCm equivalents
   ```

4. **The bottleneck = the resource that's hot *and* saturated (or erroring).**
   Only then profile it (flamegraph / drill-down / off-CPU — see
   `references/methodologies.md`). Feed the one scalar it gives you (p99, %util,
   queue depth) into an **`andrej`** loop to drive the fix and prove it stuck.

## References

- `references/use-method.md` — the USE method in depth: the three metric types and
  how to interpret each, the complete resource list, the strategy flowchart, the
  functional block diagram, software resources, cloud/virtualization limits, and
  the caches caveat.
- `references/linux-checklist.md` — the full **USE Method Linux checklist**: the
  exact command(s) for every (resource × utilization/saturation/errors) cell —
  CPU, memory, network, storage I/O & capacity, controllers, interconnects, plus
  software resources (kernel/user mutex, task capacity, file descriptors) — and the
  60-second triage checklist and the observability-tool map.
- `references/gpu-checklist.md` — USE applied to **GPUs**: NVIDIA via `nvidia-smi`,
  `nvidia-smi dmon`/`pmon`, `--query-gpu`, DCGM (`dcgmi dmon`, `dcgm-exporter`,
  field IDs), XID/ECC/retired-pages errors, NVLink/PCIe counters & topology,
  throttle reasons, and profilers (Nsight Systems/Compute); AMD ROCm equivalents.
- `references/methodologies.md` — the rest of the toolkit and what to use *instead
  of* guessing: TSA (thread-state), workload characterization, drill-down analysis,
  latency analysis, off-CPU analysis, CPU/off-CPU flame graphs, the RED method for
  services, and the named **anti-methods** to avoid (streetlight, drunk-man,
  blame-someone-else, random-change).

## Templates

- `templates/use-worksheet.md` — a fill-in worksheet: the resource list with a
  U/S/E cell per resource, a verdict column, and a functional-block-diagram slot,
  so an investigation is complete and auditable.
- `templates/60s-triage.sh` — a runnable, annotated 60-second triage script (the
  ten commands above) that prints what to look for in each.

### External sources

- Brendan Gregg, **The USE Method** — `brendangregg.com/usemethod.html`; the Linux
  checklist — `brendangregg.com/USEmethod/use-linux.html`.
- Brendan Gregg, **TSA Method** — `brendangregg.com/tsamethod.html`; **Flame
  Graphs** — `brendangregg.com/flamegraphs.html`; **off-CPU analysis**,
  `bcc`/`bpftrace` tools, and the book *Systems Performance* (2nd ed.).
- The **60-second checklist** (Netflix TechBlog, "Linux Performance Analysis in
  60,000 Milliseconds").

> **Provenance.** This skill was distilled from the four pages above (USE method,
> USE Linux checklist, TSA, 60-second) plus general systems-performance knowledge
> — it is **not** a page-by-page crawl of brendangregg.com. The
> GPU / `nvidia-smi` / DCGM / NVLink, flame-graph, and bcc/`bpftrace` tooling
> content is knowledge-derived; verify exact flags and field IDs against current
> vendor/tool docs before relying on them.

## Relationship to andrej & terry

Brendan tells you **WHICH resource to attack and WHAT to measure**; **`andrej`**
is the loop that drives the fix from that measurement and proves it stuck. They
compose directly:

- A USE sweep ends with one **scalar** (p99 latency, `%util`, queue depth, val
  throughput). That scalar is exactly the `metric` an Andrej iteration gates
  keep-or-revert on — Brendan picks the metric, Andrej moves it.
- Brendan's **structured signals** (a `--query-gpu` CSV stream, `sar`/`iostat`
  counters, DCGM exporter) are the *structured polling* Andrej prefers over
  log-grep, and Brendan's "report the real numbers" is Andrej's *verify-before-
  claim*.
- Under **`terry`**, Brendan is what a worker runs to localize a perf bottleneck
  in its scoped task before iterating; the fleet then runs many such loops in
  parallel. Use **Brendan to find the bottleneck**, **Andrej to fix one**, and
  **terry to fix many at once**.
