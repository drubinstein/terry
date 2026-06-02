#!/usr/bin/env python3
"""Generic run-metric analyzer — turn a run's signal into root-cause facts.

This is a DOMAIN-AGNOSTIC skeleton for the ANALYZE step of the
observe -> analyze -> act loop. Point it at a run's metric/event stream (a log,
a JSONL, an endpoint dump) and it ranks the signal into the four facts that pick
your next action instead of eyeballing scrollback:

  - HOTSPOT / SINK   : the most-visited node (where the loop is stuck / spending)
  - OSCILLATION      : the highest back-and-forth A<->B transition (no progress)
  - SPIKE            : WHEN a node got hammered (per-window delta), not the total
  - FINAL STATE      : the scalar metric + end position/flags (gate + evidence)

ADAPT THIS to your domain by editing only the PARSE PATTERNS in `parse()`:
emit a grep-stable metric stream from your run (see
references/metrics-and-hotspot-analysis.md) and match it here. Everything below
parse() is domain-independent ranking.

Usage:
    python3 analyze-metrics.py <run.log>           # human-readable facts
    python3 analyze-metrics.py <run.log> --json    # machine-readable facts
    your-run --metrics | python3 analyze-metrics.py -   # read stdin

Default expected stream format (CHANGE to match your run):
    metric_visits   <node>            <count>
    metric_bounce   <a> <-> <b>       <count>
    metric_delta    t=<window>  <node>  <delta>
    FINAL  metric=<scalar>  pos=<position>  flags=<flags>
"""
import json
import re
import statistics
import sys
from collections import defaultdict

# ----------------------------------------------------------------------------
# PARSE PATTERNS — the ONLY domain-specific part. Edit these to match the
# metric/event stream YOUR run emits. The names ("node", "metric") are generic
# on purpose; map them to your concepts (a map id, a service, a test file, ...).
# ----------------------------------------------------------------------------
RE_VISIT = re.compile(r"metric_visits\s+(\S+)\s+(\d+)")
RE_BOUNCE = re.compile(r"metric_bounce\s+(\S+)\s*<->\s*(\S+)\s+(\d+)")
RE_DELTA = re.compile(r"metric_delta\s+t=(\d+)\s+(\S+)\s+(\d+)")
RE_FINAL = re.compile(r"FINAL\s+metric=(\S+)\s+pos=(\S+)\s+flags=(\S+)")

# Thresholds for the heuristic flags. Tune to your domain.
SPIKE_DELTA = 5          # per-window delta >= this is a "spike"
SINK_RATIO = 3.0         # top node visited >= this x the median is a "sink"
TOP_N = 8


def node_name(raw):
    """Hook to prettify a raw node token (e.g. hex id -> human name).

    Default is identity. Override with a lookup table for your domain, e.g.:
        return f"{raw}({NAMES.get(raw, '?')})"
    """
    return raw


def parse(text):
    """Extract the raw signal. Edit the regexes above, not this structure."""
    visits = {}
    for node, n in RE_VISIT.findall(text):
        visits[node] = int(n)

    bounces = {}
    for a, b, n in RE_BOUNCE.findall(text):
        bounces[(a, b)] = int(n)

    deltas = defaultdict(dict)  # {window: {node: delta}}
    for window, node, d in RE_DELTA.findall(text):
        deltas[int(window)][node] = int(d)

    final = None
    m = RE_FINAL.search(text)
    if m:
        final = {"metric": m.group(1), "pos": m.group(2), "flags": m.group(3)}

    return visits, bounces, dict(deltas), final


def analyze(visits, bounces, deltas):
    """Rank the raw signal into facts. Domain-INDEPENDENT."""
    facts = {}

    # HOTSPOT / SINK — most-visited node; flag a sink if it dwarfs the median.
    ranked_visits = sorted(visits.items(), key=lambda kv: -kv[1])
    facts["top_visits"] = ranked_visits[:TOP_N]
    if ranked_visits:
        median = statistics.median(visits.values()) or 1
        top_node, top_n = ranked_visits[0]
        if top_n >= SINK_RATIO * median:
            facts["sink"] = (top_node, top_n, round(top_n / median, 1))

    # OSCILLATION — highest A<->B transition counts.
    facts["top_bounces"] = sorted(
        ((k, v) for k, v in bounces.items() if v > 0), key=lambda kv: -kv[1]
    )[:5]

    # SPIKE — biggest per-window deltas (WHEN a node was hammered).
    spikes = [
        (w, node, d)
        for w, by_node in deltas.items()
        for node, d in by_node.items()
        if d >= SPIKE_DELTA
    ]
    facts["spikes"] = sorted(spikes, key=lambda x: -x[2])[:10]
    facts["delta_windows"] = len(deltas)
    return facts


def render(facts, final):
    out = []
    if final:
        out.append(f"FINAL: metric={final['metric']} pos={final['pos']} "
                   f"flags={final['flags']}")
    else:
        out.append("FINAL: not present (run still going / no FINAL line)")

    if not facts.get("top_visits"):
        out.append("(no metric stream found — is the run emitting --metrics?)")
        return "\n".join(out)

    if "sink" in facts:
        node, n, ratio = facts["sink"]
        out.append(f"\nSINK: {node_name(node)} visited {n} ({ratio}x median) "
                   f"-> the loop is STUCK here; investigate this node first")

    out.append("\nTop visits (hotspot):")
    for node, n in facts["top_visits"]:
        out.append(f"  {node_name(node):<22} {n}")

    if facts["top_bounces"]:
        out.append("\nTop bounces (oscillation — no net progress):")
        for (a, b), n in facts["top_bounces"]:
            out.append(f"  {node_name(a)} <-> {node_name(b)}  {n}")

    if facts["spikes"]:
        out.append(f"\nSpikes (delta >= {SPIKE_DELTA} per window — WHEN hammered):")
        for w, node, d in facts["spikes"]:
            out.append(f"  t={w:>9}  {node_name(node):<22} delta={d}")
    elif facts["delta_windows"]:
        out.append(f"\n(no per-window spikes >= {SPIKE_DELTA}; "
                   f"{facts['delta_windows']} delta windows)")
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)

    src = args[0]
    text = sys.stdin.read() if src == "-" else open(src).read()

    visits, bounces, deltas, final = parse(text)
    facts = analyze(visits, bounces, deltas)

    if as_json:
        print(json.dumps({"final": final, **facts}, default=list, indent=2))
    else:
        print(render(facts, final))


if __name__ == "__main__":
    main()
