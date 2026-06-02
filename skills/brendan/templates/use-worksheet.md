# USE Method worksheet — <SYSTEM / HOST / JOB>

> Copy this file per investigation. Walk EVERY resource. A resource is "done" only
> when U, S, and E each have a value + verdict. The bottleneck is the resource
> that is **hot AND saturated (or erroring)** — don't stop at the first 100%.
> Order per row: **Errors → Utilization → Saturation.** See
> `references/linux-checklist.md` (Linux commands) and `references/gpu-checklist.md`.

- **Date / context:** <when, what changed, what symptom>
- **Scalar to drive the fix (hand to `andrej`):** <p99 ms | %util | queue depth | tokens/s>
- **Functional block diagram (sketch buses + max bandwidths):**

  ```
  [CPUs]==CPU-interconnect==[CPUs]
     ||                        ||
  [memory bus]            [memory bus]
     ||                        ||
  [DRAM]                    [DRAM]
     \____ I/O interconnect (PCIe x__ genN = __ GB/s) ____/
                    ||              ||
              [NIC __Gb/s]   [HBA/NVMe __GB/s]   [GPU SM/HBM/NVLink]
  ```

## Physical resources

| Resource | Errors (check first) | Utilization | Saturation | Verdict |
|----------|----------------------|-------------|------------|---------|
| CPU | | | | |
| Memory capacity | | | | |
| Network interface | | | | |
| Storage device I/O | | | | |
| Storage capacity | | | | |
| Storage controller | | | | |
| Network controller | | | | |
| CPU interconnect | | | | |
| Memory interconnect | | | | |
| I/O interconnect (PCIe) | | | | |

## GPU resources (if applicable)

| Resource | Errors | Utilization | Saturation | Verdict |
|----------|--------|-------------|------------|---------|
| GPU compute / SM | XID? ECC? | sm% / SM_ACTIVE | kernels queued? SMs under-fed? | |
| GPU memory capacity | ECC / retired pages | mem.used/total | CUDA OOM / eviction? | |
| GPU memory bandwidth | ECC | DRAM_ACTIVE / mem% | bandwidth-bound? | |
| PCIe interconnect | replays | tx/rx vs gen×width | H2D/D2H stalls? | |
| NVLink interconnect | CRC/replay (`nvlink -e`) | tx/rx bytes | imbalanced placement? | |
| Power / thermal | viol. counters | draw/limit, temp | throttle reason active? | |

## Software resources

| Resource | Errors | Utilization | Saturation | Verdict |
|----------|--------|-------------|------------|---------|
| Mutex / lock | | hold time | threads waiting | |
| Thread / worker pool | | busy-thread time | requests queued | |
| Task / process capacity | fork failures | count vs threads-max | alloc blocking | |
| File descriptors | EMFILE | open vs ulimit -n | (n/a) | |
| Imposed limits (cgroup/cloud) | | usage vs cap | throttled at cap? | |

## Conclusion

- **Bottleneck resource:** <the hot ∧ saturated/erroring one>
- **Evidence (paste the real numbers):** <e.g. r=24 on 8 CPUs; %usr=95; iostat %util=4>
- **Ruled out:** <resources confirmed clear, so a symptom isn't mistaken for cause>
- **Next:** profile it (flame graph / drill-down / off-CPU) and start an `andrej`
  loop on the scalar above.
