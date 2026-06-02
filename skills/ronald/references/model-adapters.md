# Model adapters — running the same prompt across providers

To compare arms fairly you need **one uniform way to run a prompt through any
model/agent** and capture the same fields. That's an adapter: a function

```
run(arm, prompt, case_inputs, seed) -> { output, cost_usd, latency_ms, tokens, meta }
```

Every adapter must pin the **same controlled settings** (temperature, system
prompt, tools) so the only thing that varies between arms is the factor under test.
Start with Claude; add Codex/Gemini by filling the same shape.

## Two modes — pick the one that matches your question

- **Completion comparison** (which *model* writes the better answer to a prompt):
  prefer the **provider APIs/SDKs** — you control temperature, system prompt, and
  max tokens exactly, with no agent tools confounding the output.
- **Agent comparison** (which *coding agent* does the task better, end to end): use
  the **CLIs** (`claude -p`, `codex exec`, `gemini -p`) as agents, pinning the same
  allowed tools and permission mode. This is the right mode for "Claude Code vs
  Codex vs Gemini on this task," and it's what `templates/ab-harness.py` defaults to.

Don't mix modes within one experiment — comparing an API completion against a
tool-using agent is a confound.

## Claude adapter (start here)

### CLI (agent mode) — uniform with Codex/Gemini CLIs

```bash
claude -p "$PROMPT" \
  --model claude-sonnet-4-6 \          # PIN the full version id, not "sonnet" (drift)
  --output-format json \               # structured: result + cost + duration + usage
  --system-prompt "$FIXED_SYSTEM" \    # identical across arms
  --allowed-tools "Read,Edit,Bash" \   # identical tool set across arms
  --permission-mode acceptEdits
```

The `--output-format json` result object carries the fields the harness records:

```jsonc
{
  "type": "result", "subtype": "success", "is_error": false,
  "result": "…the model's answer…",     // -> output
  "total_cost_usd": 0.0123,             // -> cost_usd
  "duration_ms": 8421,                  // -> latency_ms
  "usage": { "input_tokens": 1200, "output_tokens": 380 }  // -> tokens
}
```

### API (completion mode) — maximal control

Use the Anthropic SDK when you want a pure completion with pinned sampling and no
tools. Hold `model`, `temperature`, `system`, and `max_tokens` identical across
arms; read `usage` for tokens and compute cost from the per-model rate. (For
Anthropic-specific patterns — prompt caching, model ids, batching — see the
`claude-api` skill.)

## Codex / Gemini adapters (the pattern; confirm flags via `--help`)

Same shape, different binary. **Verify the exact flags against each CLI's current
`--help` before trusting them** — they change, and getting an arm's invocation
subtly wrong is a confound that silently handicaps it.

```bash
# OpenAI Codex CLI (agent mode), non-interactive:
codex exec "$PROMPT" --model <id>            # confirm: subcommand + model flag + how to get JSON/usage

# Gemini CLI (agent/print mode):
gemini -p "$PROMPT" --model <id>             # confirm: print flag + model flag + structured output
```

For each: pin the model **version id**, the temperature/sampling, the system prompt,
and the tool set to match the other arms as closely as the provider allows; capture
output + cost + latency + tokens (parse the provider's usage/cost if exposed, else
time the call and compute cost from token counts × the published rate).

## Fairness checklist (per arm)

- [ ] **Same prompt template** rendered identically (only the arm's varying factor differs)
- [ ] **Pinned model version id** (not a moving alias) — recorded in results
- [ ] **Same temperature / sampling** set explicitly
- [ ] **Same system prompt** (explicit, not the provider default)
- [ ] **Same tool set / permissions** (agent mode)
- [ ] **Same max output budget**
- [ ] Capture `output`, `cost_usd`, `latency_ms`, `tokens`, and the full `meta`
      (versions, settings) for every run
- [ ] All arms run in **one time window**, interleaved (not arm-A-Monday,
      arm-B-Friday)

## Capturing cost & latency (so quality isn't the only axis)

Always record cost and latency alongside the output — the decision is usually a
**tradeoff**, not pure quality. If a provider doesn't expose cost, compute it:
`cost = input_tokens × in_rate + output_tokens × out_rate` from the published
per-model pricing, and time the call wall-clock for latency. A 2-point quality win
at 5× cost and 3× latency is often a *loss*; you can't see that without these axes.

## A note on determinism

Even at `temperature = 0`, LLM outputs are **not guaranteed identical** run to run
(batching, hardware, MoE routing). So `temperature = 0` reduces variance but does
**not** remove the need to replicate (`N > 1`). Don't treat one temp-0 run as
ground truth. (See `experimental-design.md` → Replication.)
