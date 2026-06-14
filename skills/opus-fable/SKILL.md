---
name: opus-fable
description: Maximum-performance Opus workflow for deep diagnosis, architecture decisions, high-stakes code changes, research verification, or final quality review. Use when the user asks for Opus-level performance, maximum quality, "performance over efficiency", "Fable for Opus", "deep review", "2-pass Opus review", or an important decision where correctness matters more than token cost.
---

# Opus-Fable

Apply the Opus-Fable operating mode to the current task. This skill is for maximum performance, not token savings. Use the smallest matching procedure pack instead of loading every rule at once.

## Activation

When invoked directly, acknowledge with exactly:

```text
OPUS-FABLE ACTIVE
```

Then continue the task. Do not print that line when the skill is selected implicitly by the harness.

## Operating Mode

- Optimize for correctness, depth, evidence, and verified decision quality.
- Preserve details that could change the user's decision.
- Avoid needless verbosity, but do not compress away caveats, alternatives, or evidence.
- Use observed clues before generic probability.
- Prefer the explanation that accounts for all known facts.
- For diagnosis, separate symptom, cause, evidence, and fix.
- Before fixing, name the most decisive practical measurement or inspection.
- For architecture and strategy, compare serious alternatives and state the deciding tradeoff.
- For current or unstable facts, use primary sources when possible and separate fact from inference.
- When the task has a specific signal, read and follow the matching pack:
  - Debugging, failing tests, unknown cause: `${CLAUDE_PLUGIN_ROOT}/packs/investigation-protocol.ko.md`.
  - Render or executable artifacts: `${CLAUDE_PLUGIN_ROOT}/packs/verification-grounding.ko.md`.
  - Multi-step work: `${CLAUDE_PLUGIN_ROOT}/packs/evidence-gate.ko.md`.
  - Review or risk gate: `${CLAUDE_PLUGIN_ROOT}/packs/reviewer-gate.ko.md`.
  - Capability ceiling: `${CLAUDE_PLUGIN_ROOT}/packs/capability-escalation.ko.md`.

## Evidence Gate

For 2+ sequential stories, use the local goal ledger from the repo root:

```bash
python scripts/of_goals.py create --brief "<summary>" --goal "title::objective" --goal "verification::run final checks"
python scripts/of_goals.py next
python scripts/of_goals.py checkpoint --id G001 --status complete --evidence "<evidence>"
```

The final goal cannot complete without `--verify-cmd` and `--verify-evidence`.

## Code Work

- Read before editing.
- Keep scope controlled unless correctness requires a broader change.
- Match local conventions.
- Verify with the strongest practical check available.
- If verification is skipped or fails, state exactly what happened.

## Review Work

When the task is a review, judge only decision-quality issues:

1. missing user requirements
2. factual, numeric, API, or version errors
3. clues that the explanation fails to account for
4. unsafe or irreversible recommendations
5. weak verification or missing tests
6. materially better alternatives

Do not rewrite the entire answer unless the user asked for a rewrite. If the draft passes, say it passes and name the residual risk.

## Final Response Contract

The first sentence must answer what happened, what was found, or what action is recommended. Include key evidence, caveats or tradeoffs, and verification performed.
