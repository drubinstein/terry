# USE Method — GPU checklist (NVIDIA & AMD)

The USE method applies to a GPU exactly as to a CPU: enumerate the GPU's
*resources* — **compute (SM) engines, device memory capacity, memory bandwidth
(DRAM), the PCIe/NVLink interconnects, and the power/thermal envelope** — and for
each check **utilization, saturation, errors**. The trap with GPUs is that the
headline `nvidia-smi` "GPU-Util" number is **time any kernel was running**, *not*
how much of the SMs were doing work — a single tiny kernel reads 100%. Use the
profiling/DCGM counters below for true occupancy.

> Quick orientation: `nvidia-smi` (snapshot) → `nvidia-smi dmon`/`pmon` (rolling) →
> `--query-gpu` CSV (scriptable stream) → **DCGM** `dcgmi dmon`/`dcgm-exporter`
> (real SM/tensor/DRAM/NVLink activity) → **Nsight** (kernel-level profile).

## NVIDIA — the core commands

```bash
nvidia-smi                       # snapshot: per-GPU Util%, Mem used/total, Pwr, Temp, P-state, procs
nvidia-smi -l 1                  # repeat the snapshot every 1s
nvidia-smi dmon                  # rolling monitor: sm% mem% enc% dec% pwr temp mclk pclk (one row/GPU/sec)
nvidia-smi dmon -s pucvmet -d 1  # groups: p=power/temp u=util(sm/mem/enc/dec) c=clocks v=power/thermal-violations m=fb/bar1-mem e=ecc+pcie-replay t=pcie-tx/rx (NVLink is separate: `nvidia-smi nvlink`)
nvidia-smi pmon -s um            # PER-PROCESS on each GPU: sm% mem% enc% dec%, plus mem used (who is using the GPU)
nvidia-smi -q                    # full detail dump (everything below, verbose)
nvidia-smi -q -d UTILIZATION,MEMORY,POWER,CLOCK,ECC,TEMPERATURE,PERFORMANCE,ROW_REMAPPER
nvidia-smi --query-gpu=index,utilization.gpu,utilization.memory,memory.used,memory.total,\
power.draw,power.limit,temperature.gpu,clocks.sm,clocks.mem,\
clocks_event_reasons.active,pcie.link.gen.current,pcie.link.width.current \
  --format=csv -l 1             # scriptable CSV stream — feed straight into an andrej metric loop
```

NVLink & topology:

```bash
nvidia-smi topo -m               # GPU↔GPU / GPU↔NIC link matrix (NV#, PIX, SYS, PHB...) — placement sanity
nvidia-smi nvlink -s             # per-link state/capabilities
nvidia-smi nvlink -g 0           # NVLink throughput COUNTERS (Tx/Rx bytes) — utilization of the interconnect
nvidia-smi nvlink -e             # NVLink ERROR counters (CRC, replay, recovery)
```

## USE table — NVIDIA GPU

| Resource | Utilization | Saturation | Errors |
|----------|-------------|------------|--------|
| **Compute / SM** | `dmon` `sm%`; DCGM `DCGM_FI_PROF_SM_ACTIVE`, `GR_ENGINE_ACTIVE`, tensor-core `PIPE_TENSOR_ACTIVE`. (Headline `utilization.gpu` = *any* kernel running, an over-count.) | kernels queued / launch latency; low SM-occupancy *despite* 100% util = under-fed SMs; `pmon` shows the contending procs | **XID** errors `dmesg \| grep -i xid` / `nvidia-smi -q -d ERROR`; kernel faults |
| **Device memory capacity** | `memory.used`/`memory.total`; `dmon` `fb`; `pmon` per-proc mem | CUDA `out of memory`; allocator eviction/spill to host; `nvidia-smi` shows ~full FB | **ECC** `nvidia-smi -q -d ECC` (volatile/aggregate, correctable vs uncorrectable); retired/remapped pages `-d ROW_REMAPPER` |
| **Memory bandwidth (DRAM)** | `dmon` `mem%` (memory-controller busy); DCGM `DRAM_ACTIVE` | bandwidth-bound kernels (Nsight Compute "Memory Throughput" near peak) | ECC on DRAM (as above) |
| **PCIe interconnect** | DCGM `PCIE_TX_BYTES`/`PCIE_RX_BYTES`; `pcie.link.{gen,width}.current` vs `.max`; `nvidia-smi dmon -s t` (rxpci/txpci) | transfers saturating PCIe gen×width; H2D/D2H stalls (Nsight Systems timeline) | PCIe replay counter `nvidia-smi -q` (Replays since reset) |
| **NVLink interconnect** | `nvidia-smi nvlink -g 0` (Tx/Rx bytes); DCGM `NVLINK_TX_BYTES`/`RX_BYTES` | links near per-link max; imbalanced `topo -m` placement | `nvidia-smi nvlink -e` (CRC/replay/recovery errors) |
| **Power / thermal** | `power.draw` vs `power.limit`; `temperature.gpu` | **throttling**: `clocks_event_reasons.*` (`hw_slowdown`, `sw_thermal_slowdown`, `hw_power_brake`, `sw_power_cap`) — non-zero = clocks capped | thermal-violation / power-violation counters in `-q`; `dmesg` thermal events |

Reading `clocks_event_reasons` (older alias `clocks_throttle_reasons`) is the key
**saturation** signal for power/thermal: if `sw_power_cap` or `hw_thermal_slowdown`
is active, the GPU is being held below its clocks — a real bottleneck even at
"100% util". XID codes (in `dmesg`) are the master **error** signal: e.g. 13/31
(memory/page fault), 43 (app error), 48/63/64 (ECC/row-remap), 79 (GPU fell off
the bus).

## DCGM — the production-grade counters

DCGM exposes the *true* activity counters (profiling-level) without running a full
profiler — the right source for SM/tensor/DRAM/NVLink **utilization** and for
fleet monitoring.

```bash
dcgmi discovery -l                       # list GPUs/NVSwitches
dcgmi dmon -e 1001,1002,1003,1004,1005,1009,1010,1011,1012 -d 1000
#   1001 GR_ENGINE_ACTIVE  1002 SM_ACTIVE  1003 SM_OCCUPANCY  1004 PIPE_TENSOR_ACTIVE
#   1005 DRAM_ACTIVE       1009 PCIE_TX_BYTES 1010 PCIE_RX_BYTES 1011 NVLINK_TX 1012 NVLINK_RX
dcgmi health -g 0 -c                     # health/error check (ECC, XID, thermal, NVLink)
dcgm-exporter                            # Prometheus exporter — scrape into Grafana for a USE dashboard
```

(`DCGM_FI_PROF_*` field IDs above; full list in NVIDIA's DCGM docs. `dcgm-exporter`
metric names are `DCGM_FI_PROF_SM_ACTIVE`, `..._PIPE_TENSOR_ACTIVE`,
`..._DRAM_ACTIVE`, `..._PCIE_*_BYTES`, `..._NVLINK_*_BYTES`.)

## Kernel-level profiling (after USE points at the GPU)

```bash
nsys profile -t cuda,nvtx,osrt,cublas python train.py   # Nsight Systems: timeline — gaps = GPU idle/starved, H2D/D2H, sync stalls
ncu --set full -o prof ./app                            # Nsight Compute: per-kernel occupancy, memory vs compute bound, roofline
```

Use **Nsight Systems** to answer "is the GPU *starved* (data-loading / CPU /
H2D-bound) vs busy?" (timeline gaps = saturation of the feed path, not the GPU),
and **Nsight Compute** to answer "is this kernel compute- or memory-bound?"
(`nvprof` is the deprecated predecessor of both.)

## AMD ROCm equivalents

```bash
rocm-smi                                   # util, VRAM, power, temp, clocks, throttle (≈ nvidia-smi)
rocm-smi --showuse --showmemuse --showpower --showtemp --showclocks
rocminfo                                   # device/agent enumeration (≈ topo)
amd-smi monitor -putvmd                    # newer CLI: power/util/temp/vram/mem-clock rolling monitor
rocprof --stats python train.py            # kernel-level profile (≈ Nsight Compute)
rocm-smi --showxgmierr                      # xGMI (Infinity Fabric) link error counters (≈ NVLink errors)
```

USE maps the same way: **CU/compute** (`rocm-smi --showuse`), **VRAM capacity**
(`--showmemuse`), **HBM bandwidth** (rocprof memory counters), **xGMI/PCIe**
interconnect (`--showxgmierr`, fabric counters), **power/thermal** (`--showpower`/
`--showtemp` + throttle status).

## GPU triage one-liner

```bash
# Is the GPU the bottleneck, or is it starved?  (errors → util → saturation → throttle)
nvidia-smi -q -d ECC,ERROR | grep -iE 'xid|uncorrectable|pending' ;\
nvidia-smi dmon -c 5 -s pucm ;\
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,power.draw,clocks_event_reasons.active --format=csv
# sm% high + clocks_event_reasons clean  → GPU-bound (profile the kernel: ncu)
# sm% low  + util.gpu high               → under-fed SMs / tiny kernels
# sm% low  + util low + timeline gaps    → GPU STARVED: data loader / CPU / H2D — fix the feed, not the GPU
# throttle reason active                 → power/thermal capped: raise limit or cool, then re-measure
```

**If STARVED** (low `sm%`/`SM_ACTIVE` with Nsight timeline gaps), the bottleneck
is the **feed path**, not the GPU — confirm on the host and switch methods:

```bash
mpstat -P ALL 1     # a pegged CPU core → data-loading / preprocessing bound
pidstat 1           # which dataloader workers are on-CPU
```

Then apply **TSA / off-CPU analysis** to the training process (a thread mostly
*Sleeping* = I/O-bound dataloader; mostly *Executing* on CPU = preprocessing-bound)
— see `references/methodologies.md`. **Step time that climbs over minutes** is a
*trend*, so read `clocks_event_reasons` and `memory.used` as a **time series**,
not one snapshot: it's usually thermal throttle engaging after warm-up, or
allocator spill/eviction as `memory.used` creeps toward full.

Feed the chosen scalar (`sm%`, `DRAM_ACTIVE`, tokens/sec, or step time) into an
**`andrej`** loop to drive and prove the fix.
