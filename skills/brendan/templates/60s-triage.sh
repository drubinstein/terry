#!/usr/bin/env bash
# 60-second Linux performance triage — Brendan Gregg's checklist, annotated.
# Each command peels a layer: load -> errors -> CPU -> memory -> disk -> net -> procs.
# Read the ">> look for" notes; then open templates/use-worksheet.md for the full
# USE sweep. Safe, read-only. Some tools need sysstat (sar/mpstat/pidstat/iostat).
#
# Usage:  bash 60s-triage.sh            # default 1s samples
#         SECS=2 bash 60s-triage.sh     # 2s samples
set -u
S="${SECS:-1}"     # sample interval seconds
N=3                # samples per interval'd command

run() {  # run() "<header>" "<look-for note>" cmd args...
  printf '\n=== %s ===\n>> %s\n' "$1" "$2"; shift 2
  if command -v "$1" >/dev/null 2>&1; then "$@"; else echo "(skip: $1 not installed)"; fi
}

echo "################  60-SECOND TRIAGE  ($(date))  ################"

run "uptime" "load avg trend 1/5/15m — rising = growing demand; compare to nCPU=$(nproc 2>/dev/null || echo '?')" \
    uptime

run "dmesg | tail" "recent kernel errors: OOM-killer, TCP/driver drops, HW/ECC faults" \
    sh -c 'dmesg 2>/dev/null | tail -20 || echo "(need root for dmesg)"'

run "vmstat ${S} ${N}" "r > nCPU = CPU saturation; si/so != 0 = swapping; high wa = I/O wait; us vs sy split" \
    vmstat "$S" "$N"

run "mpstat -P ALL ${S} ${N}" "per-CPU balance — one hot CPU hides in the average; watch %sys %iowait %steal" \
    mpstat -P ALL "$S" "$N"

run "pidstat ${S} ${N}" "per-process CPU, rolling — who is on-CPU right now (better than a top snapshot)" \
    pidstat "$S" "$N"

run "iostat -xz ${S} ${N}" "per-disk: %util (busy), avgqu-sz>1 & await (saturation/latency), r/s+w/s, kB/s" \
    iostat -xz "$S" "$N"

run "free -m" "'available' is the real headroom; low free + high si/so above = memory pressure" \
    free -m

run "sar -n DEV ${S} ${N}" "NIC rxkB/s txkB/s vs link max = utilization; sustained near max = saturation" \
    sar -n DEV "$S" "$N"

run "sar -n TCP,ETCP ${S} ${N}" "conn rate active/passive; retrans/s > 0 = network saturation/loss" \
    sar -n TCP,ETCP "$S" "$N"

run "top -bn1 (head)" "final sanity: top consumers and their state (R/D/S)" \
    sh -c 'top -bn1 2>/dev/null | head -15'

# GPU bonus layer (only if an NVIDIA GPU is present)
if command -v nvidia-smi >/dev/null 2>&1; then
  run "nvidia-smi dmon -c ${N}" "GPU: sm%(compute) mem%(bw) pwr temp; sm% low + util high = under-fed SMs" \
      nvidia-smi dmon -c "$N" -s pucm
  run "nvidia-smi throttle/ECC" "throttle reason active = power/thermal capped; XID/ECC = errors" \
      sh -c 'nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,clocks_event_reasons.active,temperature.gpu --format=csv 2>/dev/null; nvidia-smi -q -d ECC 2>/dev/null | grep -iE "uncorrectable|pending" | head'
fi

echo
echo "################  next: USE sweep -> templates/use-worksheet.md  ################"
echo "# Bottleneck = the resource that is HOT *and* SATURATED (or erroring)."
echo "# Then profile it (flame graph / off-CPU) and drive the fix with an andrej loop."
