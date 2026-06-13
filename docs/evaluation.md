# Evaluation Plan

Use this evaluation to decide whether Opus-Fable improves outcomes rather than merely sounding more careful.

## Test Arms

Run each task through:

1. Base Sonnet or base Codex
2. Sonnet/Codex with VFF-style short discipline
3. Opus baseline
4. Opus-Fable
5. Sonnet/Codex draft with Opus reviewer

## Task Mix

Include at least:

- intermittent production bug diagnosis
- failing test with misleading error output
- architecture tradeoff decision
- security-sensitive code review
- current API or pricing research
- long technical document synthesis
- migration plan with rollback risk
- user-facing Korean explanation with exact length constraints

## Scoring

Score 1 to 5 for each:

- requirement coverage
- use of observed clues
- factual correctness
- diagnosis quality
- alternative comparison
- verification strength
- residual risk clarity
- actionability

Record token usage and wall time separately. Opus-Fable is allowed to cost more; it must justify that cost through fewer missed issues, better decisions, or stronger verification.

