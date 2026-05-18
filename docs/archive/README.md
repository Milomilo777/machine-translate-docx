# Archived documentation

This folder holds **historical** documentation — point-in-time audit reports, session-state handoffs, and one-off design proposals that are no longer the current source of truth.

These files are kept for two reasons:

1. **Provenance.** Some commits reference them — e.g., the audit notes explain why specific fixes look the way they do.
2. **Reproducibility.** When investigating an old issue, the session-state notes record what was on disk at that point in time.

## When to read something here

- You're investigating a specific commit and the message references one of these files
- You're trying to understand why a constraint (C1-C39) was introduced
- You're tracing the history of a refactor (Sprint A, Sprint D, etc.)

## When NOT to read something here

- You want to know how the project works today → [`../quickref.md`](../quickref.md) + [`../architecture.md`](../architecture.md)
- You want the current configuration → [`../configuration.md`](../configuration.md)
- You want the current invariants → [`../../PROJECT_MEMORY.md`](../../PROJECT_MEMORY.md)
- You want the current audit baseline → [`../deep-debug-audit-2026-05-18.md`](../deep-debug-audit-2026-05-18.md)

## Categories of files here

| Category | What it is |
|---|---|
| `audit-*` | One-shot audit reports from a specific date |
| `jules-*`, `codex-*` | Third-party agent audits |
| `session-state-*` | Snapshots of project state at the end of a working session |
| `agent-*` | Agent-to-agent handoff protocols (superseded by current CLAUDE.md / AGENTS.md) |
| `*-handoff.md` | Cross-session handoff notes from older sprints |
| `analysis-raw.md` | Raw analysis of the original entry script |
| `phase-F-blocked.md`, `*-followups.md`, `*-proposal.md` | One-off proposals — most have either landed or been deferred |
| `v2-frontend-hardening.md`, `v2-backend-todo.md` | Sprint-specific TODO lists (both shipped) |
| `prompt-rewrite-*`, `*-prompt-v2-*` | Iteration-specific prompt design notes |

If you find yourself reaching here often, that's a signal that something current is missing from the active docs — let's promote it back out of the archive.
