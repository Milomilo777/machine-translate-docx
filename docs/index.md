# Documentation index

The repo's deeper documentation. Pick by what you're doing.

> **Three tiers below** — `⭐ Start here`, `📂 Active reference`, and `🗄️ Archived` (history, kept for provenance only).

---

## ⭐ Start here — read these first (in order)

| File | Time | Purpose |
|---|---|---|
| [`quickref.md`](quickref.md) | 1 min | The whole repo on one page — entry points, engines, models, tests, key env vars |
| [`../CLAUDE.md`](../CLAUDE.md) | 5 min | The project router — architecture overview + key paths + conventions |
| [`architecture.md`](architecture.md) | 10 min | Full pipeline + data flow + every key path |
| [`../PROJECT_MEMORY.md`](../PROJECT_MEMORY.md) | 10 min | Active invariants C1–C39 (the things you can't break) + recent changes |
| [`configuration.md`](configuration.md) | reference | Every env var + tuning constant in one table |

---

## 📂 Active reference — read on demand

### Getting started

| File | Purpose |
|---|---|
| [`../README.md`](../README.md) | Project hero + quick start + architecture diagrams |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Dev setup, pre-commit checklist, invariants |
| [`testing.md`](testing.md) | How to run unit tests, smoke tests, and live engine tests |
| [`../SECURITY.md`](../SECURITY.md) | Vulnerability reporting + active security measures |

### Architecture

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Full pipeline + data flow + every key path |
| [`uml.md`](uml.md) | Mermaid UML diagrams — class, sequence, activity, deployment |
| [`diagrams/`](diagrams/) | 6 high-level SVG diagrams (architecture / pipeline / failure path × light + dark). *Last refreshed 2026-05-16 — predates this week's stream-hardening + circuit breaker additions. Schedule for refresh after the next real translation test.* |
| [`decisions-2026.md`](decisions-2026.md) | Architectural decision log (ADRs) |
| [`refactor-roadmap.md`](refactor-roadmap.md) | Phase A → G design rationale |

### Translation domain knowledge

| File | Purpose |
|---|---|
| [`translation-style.md`](translation-style.md) | Persian broadcast-quality rules |
| [`subtitle-syncing.md`](subtitle-syncing.md) | The bilingual aligner algorithm + thresholds |
| [`rtl-rendering.md`](rtl-rendering.md) | RTL / bidi handling in docx output |
| [`aligner-research.md`](aligner-research.md) | Background research for the Persian aligner |
| [`roadmap-persian-double-lines.md`](roadmap-persian-double-lines.md) | The 15-phase Persian Double Lines roadmap |

### Operations + observability

| File | Purpose |
|---|---|
| [`telegram-alerts-setup.md`](telegram-alerts-setup.md) | Step-by-step Telegram bot setup + security + multi-recipient |
| [`error-catalog.md`](error-catalog.md) | Known bugs (E1–E16) + status |
| [`real-engine-test-findings.md`](real-engine-test-findings.md) | Live engine test pass + bug catalog |
| [`server-deploy.md`](server-deploy.md) | Server-side deployment notes |

### API + engines + frontend

| File | Purpose |
|---|---|
| [`batch-api-analysis.md`](batch-api-analysis.md) | OpenAI Batch API evaluation |
| [`v2-improvements.md`](v2-improvements.md) | Design proposals for the v2 SPA + redesign |
| [`v2-future-ideas.md`](v2-future-ideas.md) | Tier 1–4 backlog for v2 SPA with cost scoring |

### Most recent baseline

| File | Purpose |
|---|---|
| [`deep-debug-audit-2026-05-18.md`](deep-debug-audit-2026-05-18.md) | Six-shard parallel audit of master after the FLYIN incident — P0/P1/P2 findings + applied fixes. **Read this for the current baseline state.** |

---

## 🗄️ Archived — history, kept for provenance only

29 historical documents have been moved to [`archive/`](archive/) on 2026-05-18. These are point-in-time records (audit reports, session-state snapshots, one-off design proposals) that are **no longer the current source of truth**.

See [`archive/README.md`](archive/README.md) for an explanation of what's there and when to read it.

If you're investigating a specific commit, the commit message will tell you which archived doc to consult. Otherwise, prefer the active reference above.
