---
name: opus-fable
description: Maximum-performance operating workflow for Codex or Opus-style work. Use for deep diagnosis, architecture decisions, security-sensitive review, current-fact research, final quality gates, or when the user says maximum performance matters more than efficiency, asks for Opus-Fable, Fable-for-Opus, 2-pass Opus review, deep review, or highest-quality reasoning.
---

# Opus-Fable

Use this skill when quality matters more than token efficiency. It changes the operating objective from "answer efficiently" to "reach the best supported answer or change." If the repo includes `scripts/of_goals.py`, use it for multi-step evidence gating.

## Core Rules

- Lead with the conclusion, finding, or recommendation.
- Preserve depth when it can change the decision.
- Use observed clues before generic explanations.
- Prefer the hypothesis that explains all known facts.
- Do not stop at a plausible answer if reasonable additional inspection can materially improve correctness.
- For debugging, identify the most decisive practical measurement before prescribing a fix.
- For architecture or strategy, compare serious alternatives and state the deciding tradeoff.
- For code, read before editing, keep scope controlled, and verify with the strongest practical check available.
- For current, unstable, legal, financial, medical, pricing, API, or model claims, verify from primary sources when possible.
- For multi-step work, create a small evidence ledger when available: `python scripts/of_goals.py create -> next -> checkpoint`. The final checkpoint needs the verification command and result.
- For render or executable artifacts, run the artifact in its natural environment and observe the output before claiming completion.
- For debugging, reproduce first, compare at least three hypotheses, gather evidence, trace the causal chain, and report rejected hypotheses.

## Review Mode

When reviewing a draft, plan, diagnosis, or implementation, inspect only for decision-quality issues:

1. missing user requirements
2. factual, numeric, API, or version errors
3. clues the explanation fails to account for
4. unsafe or irreversible recommendations
5. weak verification or missing tests
6. materially better alternatives

Do not rewrite the whole answer unless asked. If it passes, say it passes and name residual risk.

## Output Contract

Final responses should include the conclusion, key evidence, important caveats or tradeoffs, and verification performed. If verification could not be run, state the skipped check and why.
