# The USE Method — in depth

> *For every resource, check **utilization**, **saturation**, and **errors**.*
> — Brendan Gregg, `brendangregg.com/usemethod.html`

The USE method is a **methodology**, not a tool: a way to produce a complete,
ordered checklist so you never (a) skip a resource or (b) stop at a symptom. It
deliberately finds **bottlenecks and errors** fast — roughly 80% of server issues
with 5% of the effort — and explicitly does *not* try to be a complete latency
analysis (for that, see `methodologies.md`).

## The three metric types

| Type | Definition | How it reads | Rule of thumb |
|------|-----------|--------------|---------------|
| **Utilization** | Average time the resource was busy servicing work, as a % over an interval. | Percent (per-device or system-wide). For storage *capacity*-type resources it's the used fraction, not time-busy. | 100% = *candidate* bottleneck (confirm via saturation — internal parallelism can read 100% and be fine); sustained **>70%** already causes queueing delay; **averages hide bursts** — 20%/5-min can be 100%/seconds. |
| **Saturation** | Degree to which the resource has **extra work it can't service**, usually queued. | Queue length or wait time. | **Any non-zero saturation deserves a look.** This is usually where the pain is. |
| **Errors** | Count of error events. | Scalar count (often a counter you diff). | **Check first** — cheapest to interpret. Include *recoverable* errors and degraded-but-redundant components (e.g. a failed disk in a still-working RAID). |

Two metrics for the same resource can disagree and both matter: a disk can be
**100% utilized** (busy) yet only mildly saturated, or **60% utilized** with a
growing queue (saturated). The saturated one is the bottleneck.

## Procedure (the strategy)

For each resource in the list below:

1. **Errors first** — non-zero or increasing? A resource with errors is suspect
   regardless of load.
2. **Utilization** — busy fraction over the interval. Watch for averaging hiding
   bursts (shorten the interval, or look at per-second / per-device).
3. **Saturation** — is work queued/waiting? Any non-zero is a signal.
4. **Interpret, then iterate** to the next resource. Cross a resource off only
   when all three are accounted for. The bottleneck is the resource that is hot
   **and** saturated (or erroring) — finish the list so a downstream *symptom*
   (e.g. high CPU caused by disk-wait) isn't mistaken for the cause.

```
                    choose a resource
                           │
              ┌────────────┼─────────────┐
           errors?      high util?     saturated?
              │             │              │
        investigate   note (avg hides   any non-zero
        (recoverable    bursts!)         → investigate
         counts too)        │              │
              └─────────────┴──────────────┘
                           │
              all three accounted for? → next resource
                           │
              list exhausted → suspect = hot ∧ saturated/erroring
```

## The complete resource list (physical)

A resource is any hardware component a workload can be limited by. The canonical
list — keep it complete:

- **CPUs** — sockets, cores, hardware threads
- **Memory capacity** — usable DRAM
- **Network interfaces** — NIC RX/TX
- **Storage device I/O** — disk/SSD ops
- **Storage capacity** — filesystem / swap space
- **Storage controllers** — HBA/RAID throughput
- **Network controllers** — NIC controller throughput
- **CPU interconnect** — between sockets (e.g. UPI/QPI/Infinity Fabric)
- **Memory interconnect** — CPU ↔ memory buses
- **I/O interconnect** — PCIe and downstream buses

**Build a functional block diagram.** Sketch components and the buses between
them, annotated with **maximum bandwidth** per link (hardware/vendor docs or
engineers often have these). The diagram (a) makes the resource list provably
complete and (b) surfaces the **interconnects** people forget — a workload can
saturate a PCIe or socket-interconnect link while every CPU and device looks idle.
Interconnect utilization is usually read from CPU performance counters (CPC/LPE):
e.g. a **cycles-per-instruction (CPI) > 5** hints at memory-stall-bound work.

## Software resources

Apply the same three lenses to software objects that can queue or cap work:

| Software resource | Utilization | Saturation | Errors |
|-------------------|-------------|------------|--------|
| **Mutex lock** | time the lock is held | threads queued waiting to acquire | — |
| **Thread / worker pool** | busy-thread time | requests queued waiting for a thread | — |
| **Process / task capacity** | current count vs max (`threads-max`) | allocations blocking on memory | fork/`pthread_create` failures |
| **File descriptors** | open vs limit (`ulimit -n`) | typically none (no queueing) | `EMFILE` on `open()`/`accept()` |

## Cloud & virtualization

In multi-tenant / containerized environments, the binding limit is often a
**soft cap**, not the physical resource:

- Check hypervisor/cgroup limits on CPU, memory, network, and storage I/O.
- A tenant can be **saturated against its quota** while the physical host reads
  idle — e.g. anonymous paging / throttling appears even though the host's page
  scanner is quiet, or CPU is throttled at the cgroup `cpu.max` while host CPUs
  are free.
- Add the imposed limits to the resource list as first-class resources.

## Caveats

- **Caches are excluded from the USE sweep.** A cache *improves* performance as it
  fills, so "utilization" of a cache doesn't behave like a resource bottleneck.
  Only after the systemic resources are cleared do you look at **cache hit
  ratios** (and even then as an optimization, not a USE cell).
- **USE finds bottlenecks and errors, not everything.** It won't localize a
  latency outlier inside an un-saturated request path — switch to latency /
  drill-down / off-CPU analysis (`methodologies.md`).
- **Utilization is interval-sensitive.** Always be conscious of the averaging
  window; re-measure at a finer granularity when a "low" number smells wrong.

## Per-resource metric crib (generic)

| Resource | Utilization | Saturation | Errors |
|----------|-------------|------------|--------|
| CPU | per-CPU & system busy % | run-queue length / scheduler latency | CPC error events (e.g. ECC) |
| Memory capacity | used / available | paging/swapping, OOM kills | physical (ECC) failures |
| Network iface | throughput vs max bandwidth | drops, overruns, backlog | RX/TX errors |
| Storage I/O | device busy % | wait-queue length, `await` | device/IO errors |
| Storage capacity | used % | (none — `ENOSPC` when full) | `ENOSPC` |
| Interconnect | throughput vs max | stall cycles | CPC error events |

The exact Linux commands for each cell are in `linux-checklist.md`; the GPU
analogues are in `gpu-checklist.md`.
