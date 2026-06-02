# Claude Code skills for software engineering

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small collection of Claude Code **skills** — reusable, named methodologies for
everyday engineering work. Each is a self-contained playbook (a `SKILL.md` plus
optional references and templates) that Claude loads on demand when your request
matches it.

## Why this exists

Claude writes code well but, under pressure, tends to *guess* — skip reproducing a
bug, theorize before measuring, shrug a failure off as "flaky," or call something
done without evidence. Each skill here encodes a disciplined methodology that
resists exactly that, distilled from real long-running agent work and generalized.
You invoke a skill by intent ("does this bug actually reproduce?", "find the
bottleneck"); Claude loads the matching playbook and follows it.

## The skills

| Skill | Reach for it when… |
|-------|--------------------|
| **[jamie](skills/jamie/SKILL.md)** | you have a bug report and need to confirm it actually reproduces before fixing it |
| **[sherlock](skills/sherlock/SKILL.md)** | a bug resists the obvious explanation — find the cause by elimination |
| **[brendan](skills/brendan/SKILL.md)** | something is slow — find the bottleneck (Brendan Gregg's USE method) |
| **[andrej](skills/andrej/SKILL.md)** | you're iterating toward a fix or metric and don't want to guess |
| **[terry](skills/terry/SKILL.md)** | you have many independent long-running tasks to run in parallel and merge |
| **[ronald](skills/ronald/SKILL.md)** | you're choosing between models or prompts — run a controlled A/B experiment, not a vibe check |

Most stand alone, but five compose into a debugging-to-fix pipeline: **jamie** (confirm
it's real) → **sherlock** (find the cause) → **brendan** (find the bottleneck) →
**andrej** (drive the fix, gated on a metric) → **terry** (run many at once). **ronald**
is the odd one out — a controlled experiment harness for picking a model or prompt with
evidence. See each skill's `SKILL.md` for the full method.

## Example

You paste a bug report: *"CSV export corrupts my file every time."* Claude recognizes
a triage task and loads **jamie** — which stops it from closing the issue after one
green run on the latest build. Instead it matches the reporter's version and file,
reproduces the crash at their data scale, and minimizes it to a one-command repro:
**CONFIRMED**. It hands that repro to **sherlock** to eliminate suspects down to the
root cause, then to **andrej** to drive the fix, gated on the repro until it passes.

## Using these skills

**As a plugin** — point your Claude Code plugin config at this repo (or a marketplace
entry that references it). The manifest at `.claude-plugin/plugin.json` auto-discovers
every `skills/*/SKILL.md`.

**As personal skills** — copy any skill directory into your user skills folder:

```bash
cp -R skills/sherlock ~/.claude/skills/sherlock   # or any other skill
```

Either way, Claude auto-discovers them and loads the right one when your request
matches its description — or invoke one explicitly with the Skill tool.

## Layout

Each skill is a directory under `skills/`:

```
skills/<name>/
  SKILL.md        # the methodology — what it's for and how to run it
  references/     # deeper detail, loaded on demand (optional)
  templates/      # copy-paste worksheets / scripts (optional)
```

The repo is named `terry` for historical reasons — it began as that single
agent-fleet skill — but it's now a general software-engineering skills collection,
and `terry` is just one of them.

## Contributing

Each skill follows the same shape — a tight `SKILL.md` with depth in `references/`
and copy-paste assets in `templates/` — and is built test-first: write a failing
scenario for a subagent, write the skill, then close the loopholes it finds. New
skills and fixes are welcome via pull request or
[issues](https://github.com/drubinstein/terry/issues).

## License

[MIT](LICENSE) © David Rubinstein

