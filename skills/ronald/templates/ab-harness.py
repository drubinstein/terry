#!/usr/bin/env python3
"""
ab-harness.py — run the SAME prompt through multiple arms (models/agents) over a
fixed case suite with N replicates, in randomized order, capturing output + cost +
latency + tokens. Writes results.jsonl for the (blinded) judging + analysis step.

This is the RUN step of an `ronald` experiment. It does NOT judge or analyze — keep
those separate so the judge can be blinded (see references/judging-and-stats.md).

Design discipline this harness enforces:
  - one varying factor (the arm); ALL other settings pinned identically below
  - the same cases through every arm (paired); N replicates per (arm x case)
  - randomized run order (so a mid-run slowdown doesn't land on one arm)
  - cost/latency/tokens captured next to quality

Starts with a working CLAUDE adapter (agent mode via `claude -p`). Codex/Gemini are
stubs — fill them to the SAME shape, and confirm each CLI's flags via `--help`.

Usage:
  python3 ab-harness.py --arms opus,sonnet --cases cases.jsonl -n 3 --out results.jsonl
  # cases.jsonl: one JSON object per line, e.g. {"case_id": "bug-01", "inputs": {"task": "..."}}
"""
import argparse, json, subprocess, time, random, sys
from collections import Counter

# --- arm -> (provider, pinned model version id) -------------------------------
# Pin FULL version ids, never moving aliases (drift is a confound).
CLAUDE_ALIASES = {
    "opus":   "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku":  "claude-haiku-4-5-20251001",
}

def resolve_arm(spec):
    """'opus' -> ('claude','claude-opus-4-8'); 'codex:gpt-x' -> ('codex','gpt-x')."""
    if ":" in spec:
        provider, model = spec.split(":", 1)
        return provider, model
    if spec in CLAUDE_ALIASES:
        return "claude", CLAUDE_ALIASES[spec]
    return "claude", spec  # assume a full claude id

# --- adapters: run(model, prompt, cfg) -> dict --------------------------------
# Every adapter returns the SAME fields. Pin cfg (system prompt, tools) identically
# across arms — that is what keeps the comparison fair.

def run_claude(model, prompt, cfg):
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--system-prompt", cfg["system_prompt"],      # identical across arms
        "--allowed-tools", cfg["allowed_tools"],       # identical across arms
        "--permission-mode", cfg["permission_mode"],
    ]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg["timeout_s"])
    wall_ms = int((time.time() - t0) * 1000)
    if p.returncode != 0:
        return {"output": None, "is_error": True, "err": p.stderr[-500:],
                "cost_usd": None, "latency_ms": wall_ms, "tokens": None,
                "model_version": model}
    d = json.loads(p.stdout)
    u = d.get("usage", {}) or {}
    return {
        "output": d.get("result"),
        "is_error": bool(d.get("is_error")),
        "cost_usd": d.get("total_cost_usd"),
        "latency_ms": d.get("duration_ms", wall_ms),
        "tokens": {"in": u.get("input_tokens"), "out": u.get("output_tokens")},
        "model_version": model,
    }

def run_codex(model, prompt, cfg):
    # TODO: same shape as run_claude. Confirm flags via `codex --help`.
    #   cmd = ["codex", "exec", prompt, "--model", model, ...]  # + structured/usage output
    # Pin the same system prompt + tool set as the other arms; parse cost/tokens if exposed,
    # else compute cost = in_tok*in_rate + out_tok*out_rate and time the call.
    # NOTE: cfg["allowed_tools"]/["permission_mode"] are Claude-CLI vocabulary — MAP them to
    #   this provider's equivalents; passing them verbatim is an unfair-arm confound.
    raise NotImplementedError("fill in the Codex adapter (see references/model-adapters.md)")

def run_gemini(model, prompt, cfg):
    # TODO: same shape. Confirm flags via `gemini --help` (e.g. `gemini -p <prompt> --model <id>`).
    # NOTE: map cfg["allowed_tools"]/["permission_mode"] to this provider's vocabulary, don't
    #   pass them verbatim — an arm with a different tool/permission set is a different agent.
    raise NotImplementedError("fill in the Gemini adapter (see references/model-adapters.md)")

ADAPTERS = {"claude": run_claude, "codex": run_codex, "gemini": run_gemini}

# --- main: build the matrix, randomize, run, record ---------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="comma list, e.g. opus,sonnet or codex:gpt-x")
    ap.add_argument("--cases", required=True, help="cases.jsonl ({case_id, inputs} per line)")
    ap.add_argument("-n", "--replicates", type=int, default=3)
    ap.add_argument("--out", default="results.jsonl")
    ap.add_argument("--prompt-template", default="{task}",
                    help="rendered per case via str.format(**inputs); keep IDENTICAL across arms")
    ap.add_argument("--system-prompt", default="", help="PINNED identical across all arms")
    ap.add_argument("--allowed-tools", default="Read,Edit,Bash")
    ap.add_argument("--permission-mode", default="acceptEdits")
    ap.add_argument("--timeout-s", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0, help="fixes the randomized run order")
    args = ap.parse_args()

    cfg = {"system_prompt": args.system_prompt, "allowed_tools": args.allowed_tools,
           "permission_mode": args.permission_mode, "timeout_s": args.timeout_s}
    arms = [(a, *resolve_arm(a)) for a in args.arms.split(",")]   # (label, provider, model)
    cases = [json.loads(l) for l in open(args.cases) if l.strip()]

    # full matrix: every arm x every case x N replicates (paired design)
    jobs = [(label, prov, model, c, r)
            for (label, prov, model) in arms
            for c in cases
            for r in range(args.replicates)]
    random.Random(args.seed).shuffle(jobs)        # randomize order across arms/cases

    written, errors = Counter(), Counter()
    expected_per_arm = len(cases) * args.replicates
    with open(args.out, "w") as out:
        for i, (label, prov, model, c, r) in enumerate(jobs, 1):
            prompt = args.prompt_template.format(**c.get("inputs", {}))
            try:
                res = ADAPTERS[prov](model, prompt, cfg)
            except NotImplementedError as e:
                print(f"[{i}/{len(jobs)}] {label}: {e}", file=sys.stderr); continue
            row = {"arm": label, "provider": prov, "case_id": c["case_id"],
                   "replicate": r, **res}
            out.write(json.dumps(row) + "\n"); out.flush()
            written[label] += 1
            if res.get("is_error"): errors[label] += 1
            tag = "ERR" if res.get("is_error") else "ok"
            print(f"[{i}/{len(jobs)}] {label} {c['case_id']} r{r} {tag} "
                  f"{res.get('latency_ms')}ms ${res.get('cost_usd')}", file=sys.stderr)

    # FAIL LOUDLY on an incomplete matrix — a missing/short arm is NOT a valid paired
    # A/B, it's a one-arm "comparison". Don't let it slip through silently.
    missing = [lbl for (lbl, _, _) in arms if written[lbl] < expected_per_arm]
    if missing:
        sys.exit(f"INCOMPLETE: arms {missing} produced < {expected_per_arm} rows "
                 f"(unfilled adapter? failures?) — {args.out} is NOT a valid paired comparison")
    if errors:
        print(f"WARNING: error rows per arm: {dict(errors)} — audit/drop them before "
              f"analysis (don't score a rate-limit failure as a quality miss)", file=sys.stderr)
    print(f"wrote {args.out} ({len(arms)} arms × {len(cases)} cases × {args.replicates} reps); "
          f"next: judge (blinded) then analyze (references/judging-and-stats.md)", file=sys.stderr)

if __name__ == "__main__":
    main()
