# Opus Fable Performance

`opus-fable-performance` is an Opus-first operating layer inspired by the Value-for-Fable idea, but rebuilt for maximum performance instead of token efficiency.

The original VFF project asks: "Can Sonnet behave more like Fable for less money?" This repository asks a different question: "Can Opus be made less shallow, less premature, and more reliably verified when quality matters more than cost?"

## What This Repo Contains

- Claude Code plugin assets: `skills/`, `agents/`, `output-styles/`, and `hooks/`.
- Codex assets: `.agents/skills/opus-fable/` and `codex/AGENTS.opus-fable.md`.
- Research notes: `docs/research.md`, `docs/routing.md`, and `docs/evaluation.md`.
- Benchmark seed set: `evals/tasks.jsonl` and `evals/rubric.md`.
- Validation script: `scripts/validate_repo.py`.

## Design Position

Opus should not inherit VFF's cost-saving posture. Opus is useful because it can inspect more, compare alternatives better, and recover from weak first hypotheses. The performance layer therefore keeps the Fable-style operating structure but changes the objective:

- Correctness over brevity.
- Decisive verification over cheap verification.
- Evidence-backed recommendation over plausible answer.
- Serious alternative comparison over premature narrowing.
- Residual risk stated plainly.

## Recommended Routing

Use this mode directly when the task has high consequence or real uncertainty:

- hard debugging and incident diagnosis
- architecture decisions
- security-sensitive or data-loss-sensitive work
- final review before deployment, migration, or publish
- research where current facts, prices, APIs, laws, or policies may have changed

Use `Sonnet/Codex draft -> Opus reviewer` when you want quality without having Opus perform all first-pass exploration. The reviewer should not rewrite style; it should only catch missing requirements, factual errors, unexplained clues, unsafe recommendations, weak verification, and materially better alternatives.

## Claude Code Install

Local development:

```bash
claude --plugin-dir /absolute/path/to/opus-fable-performance
```

Plugin marketplace install, after publishing this repository as a Claude Code marketplace:

```text
/plugin marketplace add <owner>/<repo>
/plugin install opus-fable-performance@<owner>
```

Manual copy:

```bash
mkdir -p ~/.claude/skills/opus-fable ~/.claude/agents ~/.claude/output-styles ~/.claude/hooks
cp skills/opus-fable/SKILL.md ~/.claude/skills/opus-fable/SKILL.md
cp agents/opus-reviewer.md ~/.claude/agents/opus-reviewer.md
cp output-styles/opus-fable.md ~/.claude/output-styles/opus-fable.md
cp hooks/opus-reminder.sh ~/.claude/hooks/opus-reminder.sh
chmod +x ~/.claude/hooks/opus-reminder.sh
```

Then choose `/config -> Output style -> Opus-Fable`, or invoke `/opus-fable` for a scoped session workflow.

## Codex Install

For a project:

```bash
mkdir -p .agents/skills
cp -r /absolute/path/to/opus-fable-performance/.agents/skills/opus-fable .agents/skills/
cp /absolute/path/to/opus-fable-performance/codex/AGENTS.opus-fable.md AGENTS.md
```

For a global preference, merge the short version from `codex/AGENTS.opus-fable.md` into `~/.codex/AGENTS.md`. Keep the global file short; the full workflow belongs in the skill.

## Source Position and Attribution

This repository is not a fork of `itsinseong/value-for-fable` and does not copy its implementation. It is a new Opus-focused adaptation based on:

- `itsinseong/value-for-fable`, which frames the Sonnet cost-performance operating layer.
- `elder-plinius/CL4R1T4S/ANTHROPIC/CLAUDE-FABLE-5.md`, which the VFF README identifies as the public Fable 5 operating-structure source.
- Current Claude Code and Codex extension documentation.

See `NOTICE.md` and `docs/research.md` for details.

## Validate

```bash
python scripts/validate_repo.py
python C:/Users/USER/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/opus-fable
```

