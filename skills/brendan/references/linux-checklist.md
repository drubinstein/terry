# USE Method — Linux checklist & tool map

The exact command(s) for every **(resource × utilization / saturation / errors)**
cell, after Brendan Gregg's Linux checklist (`brendangregg.com/USEmethod/use-linux.html`).
Pick the cell you need; don't run everything. Counters (errors, paging) are
usually *cumulative* — diff two samples or run with an interval.

## The 60-second triage (run first)

```bash
uptime                  # load avg trend (1/5/15 min). Rising = growing demand.
dmesg | tail            # recent kernel errors: OOM-killer, TCP drops, driver/HW faults
vmstat 1                # r=runq (≫ nCPU ⇒ CPU saturation); si/so≠0 ⇒ swapping; wa ⇒ I/O wait; us/sy split
mpstat -P ALL 1         # per-CPU util — find one hot CPU the average hides; high %sys / %iowait / %steal?
pidstat 1               # per-process CPU, rolling — who is on-CPU right now (better than a top snapshot)
iostat -xz 1            # per-disk: %util, avgqu-sz, await/r_await/w_await, r/s+w/s, rkB/s+wkB/s
free -m                 # memory: "available" is the real number; buff/cache reclaimable
sar -n DEV 1            # NIC rxkB/s txkB/s vs link max ⇒ utilization; rxpck/txpck
sar -n TCP,ETCP 1       # active/s passive/s conn rate; retrans/s (saturation/error); iseg/oseg
top                     # final sanity: top consumers and their state
```

(Modern equivalents: `pidstat`, `bpftrace`/`bcc`, `tcplife`, `biolatency`,
`btop`/`htop` — but the above are present almost everywhere.)

> **Two gotchas.** (1) The **first** `vmstat`/`mpstat`/`iostat` sample is the
> *since-boot average* — ignore it, read from the second sample on (matters most
> right after a deploy, where the boot average dilutes the new signal). Append a
> count to avoid hanging: `vmstat 1 5`. (2) A high **load average** is *not* proof
> of CPU saturation — Linux load counts uninterruptible-sleep (D-state, I/O-bound)
> threads too; disambiguate with `vmstat` `r` (run-queue) vs `wa` / `iostat`
> before blaming CPU.

---

## Physical resources

### CPU
- **Utilization:** `vmstat 1` (`us`+`sy`+`st`); `mpstat -P ALL 1` (per-CPU `%idle`);
  `sar -u`; `pidstat 1`; `top`/`htop` (%CPU). System-wide *average* can hide a
  single saturated CPU — always check per-CPU.
- **Saturation:** `vmstat 1` (`r` > CPU count); `sar -q` (`runq-sz`, `ldavg-*`);
  `/proc/<PID>/schedstat` (2nd field = time waiting on run-queue); `perf sched
  latency`; `getdelays`/delay accounting.
- **Errors:** `perf` with processor-specific CPC events; machine-check errors via
  `dmesg`/`ras-mc-ctl --summary` (ECC).

### Memory capacity
- **Utilization:** `free -m`; `vmstat 1` (`free`, `buff`, `cache`); `sar -r`
  (`%memused`); `slabtop -s c` (kernel slab); `top`/`htop` (RES/VIRT per process);
  `/proc/meminfo`.
- **Saturation:** `vmstat 1` (`si`/`so` = swap-in/out — anonymous paging is the
  key saturation signal); `sar -B` (`pgscank`+`pgscand` = page scanning under
  pressure); `sar -W`; `dmesg | grep -i kill` (OOM-killer); `/proc/<PID>/stat`
  field 10 (`majflt`).
- **Errors:** `dmesg` (physical/ECC failures); dynamic tracing of failed
  `malloc()` / page-fault errors.

### Network interfaces
- **Utilization:** `sar -n DEV 1` (`rxkB/s`,`txkB/s` vs interface max);
  `ip -s link` (RX/TX bytes); `/proc/net/dev`; `nicstat` (`%Util`).
- **Saturation:** `nstat`/`netstat -s` (drops, pruning, backlog); `sar -n EDEV 1`
  (`*drop`,`*fifo`); `ifconfig` (`overruns`,`dropped`); NIC ring `ethtool -S`.
- **Errors:** `ip -s link` / `ifconfig` (`errors`,`dropped`); `netstat -i`
  (`RX-ERR`,`TX-ERR`); `sar -n EDEV 1`; `/sys/class/net/<if>/statistics/*`.

### Storage device I/O
- **Utilization:** `iostat -xz 1` (`%util`); `sar -d`; `iotop`; `pidstat -d 1`
  (per-process I/O); `/proc/<PID>/io`. **Caveat:** `%util` = fraction of time ≥1
  I/O was in flight; for devices that service I/O in parallel (NVMe/SSD, RAID &
  array LUNs, virtual disks) **100% `%util` does *not* mean saturated** — judge
  saturation by the queue, not `%util`.
- **Saturation:** `iostat -xnz 1` (`avgqu-sz` (newer sysstat: `aqu-sz`) > 1,
  rising `await`/`r_await`/`w_await`); `sar -d`; block-layer tracing
  (`biolatency`, `biosnoop`, `blktrace`).
- **Errors:** `/sys/devices/.../<dev>/ioerr_cnt`; `smartctl -a <dev>` (SMART
  reallocated/pending sectors); `dmesg` I/O errors; SCSI error tracing.

### Storage capacity (filesystem / swap)
- **Utilization:** `df -h` (filesystems); `swapon -s` / `free` /
  `/proc/meminfo` (`SwapFree`/`SwapTotal`); inode usage `df -i`.
- **Saturation:** essentially none — once full you get `ENOSPC`, not a queue.
- **Errors:** `strace`/dynamic tracing for `ENOSPC`; `/var/log/messages`,
  `dmesg` (filesystem-full / read-only remounts).

### Storage controller (HBA/RAID)
- **Utilization:** `iostat -xz 1` summing device throughput vs the controller's
  known max (IOPS / MB/s).
- **Saturation / Errors:** see storage-device saturation/errors; plus
  vendor tools (`storcli`/`megacli`, `nvme` log) for controller-level counters.

### Network controller
- **Utilization:** infer from `ip -s link` / `/proc/net/dev` summed vs the
  controller's max bandwidth.
- **Saturation / Errors:** see network-interface saturation/errors.

### CPU / Memory / I/O interconnects
- **Utilization:** CPU performance counters (CPC via `perf`/LPE) — throughput vs
  max; a **CPI > 5** suggests memory-stall-bound work; `perf stat -e` with
  uncore/IMC events; `pcm`/`pcm-memory` (Intel), `amd_uprof` (AMD).
- **Saturation:** CPC stall-cycle events (`perf stat` stalled-cycles-*).
- **Errors:** CPC error events where available.

---

## Software resources

### Kernel mutex
- **Utilization:** `/proc/lock_stat` (`holdtime-total`/`acquisitions`) — requires
  `CONFIG_LOCK_STAT=y`.
- **Saturation:** `/proc/lock_stat` (`waittime-total`/`contentions`);
  `perf record -a -g -F 997` (off-CPU/lock stacks).
- **Errors:** dynamic tracing; `kdump`/`crash` after a lockup/panic.

### User-space mutex
- **Utilization:** `valgrind --tool=drd --exclusive-threshold=<ms>` (hold time).
- **Saturation:** `valgrind --tool=drd`; dynamic tracing of `pthread_mutex_lock`
  latency (`bpftrace`/`bcc`); `perf` lock events.
- **Errors:** `valgrind --tool=drd`; trace `pthread_mutex_*` return codes.

### Task capacity (processes/threads)
- **Utilization:** `top`/`htop` (Tasks); `sysctl kernel.threads-max` /
  `/proc/sys/kernel/threads-max`; `ps -eLf | wc -l`; cgroup `pids.current`.
- **Saturation:** allocation blocking on memory; `sar -B` page scanning.
- **Errors:** `fork()` failures (`EAGAIN`); `pthread_create()` failures;
  `dmesg` (`fork: Resource temporarily unavailable`).

### File descriptors
- **Utilization:** **per-process** (the usual `EMFILE` cause) `ls /proc/<PID>/fd
  | wc -l` vs `ulimit -n` / `cat /proc/<PID>/limits`; **system-wide** `sar -v`
  (`file-nr`) / `/proc/sys/fs/file-nr` vs `sysctl fs.file-max`. The "Too many open
  files" you hit under load is almost always the **per-process** cap, so check it
  first (`file-nr` usually looks healthy and misleads).
- **Saturation:** none — descriptors don't queue.
- **Errors:** `strace`/tracing for `EMFILE` on `open()`/`accept()`/`socket()`.

---

## Observability tool map (where each tool fits)

| Layer | Counters / snapshots | Tracing / latency | Profiling |
|-------|----------------------|-------------------|-----------|
| **CPU** | `vmstat`,`mpstat`,`sar -u`,`pidstat` | `perf sched`, `runqlat` (bcc) | `perf record -F 99 -ag`, `profile` (bcc) → **CPU flame graph** |
| **Memory** | `free`,`vmstat`,`sar -r/-B`,`slabtop` | `funccount`, page-fault tracing | `perf mem`, heap profilers |
| **Disk** | `iostat -xz`,`sar -d`,`pidstat -d` | `biolatency`,`biosnoop`,`blktrace` | block-layer flame graphs |
| **Net** | `sar -n DEV/TCP`,`nicstat`,`nstat` | `tcplife`,`tcpretrans`,`tcptop` | off-CPU/network flame graphs |
| **Whole-system** | `dstat`,`sar -A`,`atop` | `bpftrace` one-liners | `perf`, `bcc/libbpf-tools` |

`perf`, `bcc` (`/usr/share/bcc/tools`), and `bpftrace` are the modern drill-down
layer once USE has named the resource — see `methodologies.md` for *how* to drill.
