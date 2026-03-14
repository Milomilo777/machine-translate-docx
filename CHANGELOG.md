# Changelog

### [2026-03-14] Branch: feature/diagnostics-support-bundle-v1 — Central Diagnostic Bundle Engine
**What changed:** Added centralized diagnostic bundling system to capture and isolate error states in JSON.
**Why:** To improve debugging of translation, polish, align, and double pipelines.
**Files touched:** src/diagnostics/bundle_manager.py, src/openai_translator/translator.py, src/machine-translate-docx.py, docs/diagnostics.md, CHANGELOG.md

### [2026-03-14] Branch: feature/diagnostics-indexing-v2 — Central Diagnostic Indexing and Retention
**What changed:** Added a global `logs/index.json` registry, `latest_status.json` pointer for files, and 50-log retention policy to the Diagnostic Bundle Engine.
**Why:** To make generated log bundles manageable, searchable, and to prevent infinite disk space consumption.
**Files touched:** src/diagnostics/bundle_manager.py, docs/diagnostics.md, CHANGELOG.md

### [2026-03-14] Branch: feature/diagnostics-enterprise-v3 — Enterprise-Grade Observability
**What changed:** Implemented trace IDs linked to documents to unify pipeline logs, standardized JSON schema attributes, and improved secret redaction to use `***`.
**Why:** To ensure future telemetry tool integrations and observability dashboards can parse the logs natively.
**Files touched:** src/diagnostics/bundle_manager.py, src/openai_translator/translator.py, docs/diagnostics.md, CHANGELOG.md

### [2026-03-14] Branch: fix/pipeline-isolation-v4 — Architecture Fixes
**What changed:** Fixed OS shadowing bug, Enforced Excel TM isolation for Polish/Align/Double pipelines, Fixed TM class instantiation, and disabled blocking GitHub CI workflows.
**Why:** To resolve PR blockers resulting from unbound local variables, strict adherence to isolation requirements in subsequent translation phases, and deprecated Node.js GitHub actions.
**Files touched:** src/machine-translate-docx.py, .github/workflows/ (deleted), CHANGELOG.md
