# Research Notes

## Source Chain

`itsinseong/value-for-fable` is a public GitHub repository described as a Claude Code project that aims to get Fable-like quality at Sonnet cost. The GitHub repository API reported `"fork": false` when inspected on 2026-06-13, so it is not marked as a fork by GitHub.

The repository README identifies the Fable operating-structure source as:

```text
elder-plinius/CL4R1T4S/ANTHROPIC/CLAUDE-FABLE-5.md
```

The README says the VFF eight-section structure was observed from that public Fable 5 system prompt and independently reconstructed. This repo follows that attribution chain but does not copy VFF implementation text.

## What VFF Gets Right

The VFF pattern is useful because it turns broad model quality into operational behavior:

- answer-first communication
- clue-driven diagnosis
- measurement before fix
- verification before completion claims
- disciplined tool use
- scoped code changes
- source-aware research
- output trimming that removes non-decision details

These are not Sonnet-specific. They are useful for Opus too.

## Why Opus Needs a Different Objective

The original VFF objective is cost-performance: make Sonnet behave more like Fable while spending less. Opus should not inherit that goal. If a user selects Opus, they usually want the stronger model to spend more thought where it matters.

Therefore this repo changes the objective from:

```text
Fable-like quality at Sonnet cost
```

to:

```text
Maximum quality from Opus through disciplined investigation, verification, and review.
```

## Official Extension Surface Checked

- Claude Code plugins can bundle skills, agents, hooks, MCP servers, LSP servers, and monitors.
- Claude Code output styles modify the system prompt and can preserve built-in coding instructions with `keep-coding-instructions: true`.
- Claude Code hooks run at lifecycle events and can receive JSON on stdin.
- Codex reads `AGENTS.md` files and supports reusable `SKILL.md` skills with progressive disclosure.
- Codex subagents are available but are explicit and cost more than single-agent runs.

## Practical Conclusion

Opus-Fable should be a performance guardrail, not a cost guardrail. Its best use is direct Opus work on hard problems and reviewer-pass work after a cheaper first draft.

