# Routing Guide

## Use Sonnet or Codex First

Use a cheaper first pass when:

- the implementation path is straightforward
- the task is documentation, formatting, or routine refactoring
- the main challenge is execution volume rather than deep judgment
- verification is easy and deterministic

Recommended route:

```text
Sonnet/Codex -> local tests -> Opus reviewer if risk remains
```

## Use Opus-Fable Directly

Use Opus-Fable as the primary worker when:

- the diagnosis depends on subtle clues
- the domain is unfamiliar or layered
- an architecture decision will be expensive to reverse
- a security, privacy, financial, legal, or data-loss risk is present
- the user asks for maximum performance
- a prior answer feels plausible but not explanatory

Recommended route:

```text
Opus-Fable -> decisive inspection -> implementation or recommendation -> strongest practical verification
```

## Use Opus Reviewer

Use the reviewer when a draft or implementation already exists and the question is "is this actually good enough?"

The reviewer should inspect for:

- missing requirements
- wrong facts or stale assumptions
- unexplained clues
- unsafe actions
- weak tests
- materially better alternatives

The reviewer should not rewrite style or expand scope unless the finding changes correctness.

