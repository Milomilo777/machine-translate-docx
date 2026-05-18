# Documentation index

The repo's deeper documentation. Pick by what you're doing.

## Getting started

| File | Purpose |
|---|---|
| [`../README.md`](../README.md) | Project hero + quick start + architecture diagrams |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Dev setup, pre-commit checklist, invariants |
| [`testing.md`](testing.md) | How to run unit tests, smoke tests, and live engine tests |
| [`../SECURITY.md`](../SECURITY.md) | Vulnerability reporting + active security measures |

## Architecture

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Full pipeline + data flow + every key path |
| [`uml.md`](uml.md) | 5 Mermaid UML diagrams — class, sequence (happy + failure), activity, deployment |
| [`diagrams/architecture-detailed-light.svg`](diagrams/architecture-detailed-light.svg) | Module-level architecture map — every package under `src/machine_translate_docx/` |
| [`diagrams/README.md`](diagrams/README.md) | The 6 high-level SVG diagrams (architecture / pipeline / failure path × light + dark) |
| [`master-audit-2026-05-16.md`](master-audit-2026-05-16.md) | Five-shard audit of master HEAD — P0/P1/P2/P3 findings + Sprint plan |
| [`refactor-roadmap.md`](refactor-roadmap.md) | Phase A → G design rationale |
| [`post-refactor-audit.md`](post-refactor-audit.md) | 15 findings from the 2026-05-08 audit |
| [`audit-2026-05-11.md`](audit-2026-05-11.md) | Comprehensive 2026-05-11 audit + applied fixes |
| [`cli-shrink-phase3-handoff.md`](cli-shrink-phase3-handoff.md) | Historical — all Sprint D tasks (statistics cluster, Google file-mode workers, `_sync_globals_from_ctx` collapse) merged to master 2026-05-17. Archive reference only. |
| [`decisions-2026.md`](decisions-2026.md) | Architectural decision log (ADRs) |
| [`../PROJECT_MEMORY.md`](../PROJECT_MEMORY.md) | Active invariants C1–C39 + recurring issues E1–E16 |

## Translation domain knowledge

| File | Purpose |
|---|---|
| [`translation-style.md`](translation-style.md) | Persian broadcast-quality rules |
| [`subtitle-syncing.md`](subtitle-syncing.md) | The bilingual aligner algorithm + thresholds |
| [`rtl-rendering.md`](rtl-rendering.md) | RTL / bidi handling in docx output |
| [`aligner-research.md`](aligner-research.md) | Background research for the Persian aligner |
| [`roadmap-persian-double-lines.md`](roadmap-persian-double-lines.md) | The 15-phase Persian Double Lines roadmap |

## Operations + observability

| File | Purpose |
|---|---|
| [`telegram-alerts-setup.md`](telegram-alerts-setup.md) | Step-by-step Telegram bot setup + security + multi-recipient |
| [`real-engine-test-findings.md`](real-engine-test-findings.md) | Live engine test pass + 4 bugs + 8 weaknesses (all resolved or parked) |
| [`error-catalog.md`](error-catalog.md) | Known bugs (E1–E16) + status |

## API + engines

| File | Purpose |
|---|---|
| [`batch-api-analysis.md`](batch-api-analysis.md) | OpenAI Batch API evaluation |
| [`analysis-raw.md`](analysis-raw.md) | Raw analysis of the original entry script (~80 globals) |
| [`v2-frontend-hardening.md`](v2-frontend-hardening.md) | 2026-05-09 v2 hardening sprint (5 phases) |

## Process / playbooks

| File | Purpose |
|---|---|
| [`playbooks/add-feature.md`](playbooks/add-feature.md) | How to ship a feature end-to-end |
| [`playbooks/fix-bug.md`](playbooks/fix-bug.md) | Bug-fix workflow |
| [`playbooks/translate-batch.md`](playbooks/translate-batch.md) | Bulk translation playbook |
| [`playbooks/update-memory.md`](playbooks/update-memory.md) | When + how to update PROJECT_MEMORY.md |
| [`agent-handoff.md`](agent-handoff.md) | Agent → agent session handoff protocol |
| [`agent-run-report.md`](agent-run-report.md) | Agent run reporting format |
| [`next-session-handoff.md`](next-session-handoff.md) | The most recent next-session handoff note |

## Strategy / external

| File | Purpose |
|---|---|
| [`../JVM_Migration_Analysis.docx`](../JVM_Migration_Analysis.docx) | Word document — analysis of a hypothetical Java + Kotlin migration |

## Historical / archived

| File | Purpose |
|---|---|
| [`phase-F-blocked.md`](phase-F-blocked.md) | Phase F1 original blocker note |
| [`PR-text.md`](PR-text.md) | Stored PR description text |

## See also

- [`../CHANGELOG.md`](../CHANGELOG.md) — chronological session log (one entry
  per landing commit; reverse-chronological).
- [`docs/diagrams/`](diagrams/) — SVG architecture diagrams; the hero
  one is embedded in the project README.
