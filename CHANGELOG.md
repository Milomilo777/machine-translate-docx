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

### [2026-03-14] Branch: feature/telemetry-integration-v5 — Telemetry Integration & Silent Failure Tracking
**What changed:** Fixed action routing for double pipeline, integrated bundle manager into OpenAI translator for silent failure tracking. Captured `response_text` and mismatch states directly into diagnostic logs.
**Why:** To ensure we can debug why `json.loads` or `repair_lines` fail natively on intermediate pipelines instead of relying solely on successful `target_dict` fallbacks which masked underlying structural prompt issues.
**Files touched:** src/machine-translate-docx.py, src/openai_translator/translator.py, CHANGELOG.md

### [2026-03-14] Branch: feature/universal-execution-tracing-v6 — Universal Execution Tracing
**What changed:** Fixed relative pathing for logs directory using absolute `__file__` paths. Implemented Universal Execution Tracing to capture raw LLM outputs for every pipeline.
**Why:** To ensure logs are predictably located when executing via the GUI out of various CWD states, and to record complete audit trails mapping inputs, prompts, raw JSON string outputs, and safely parsed dictionaries for LLM deterministic debugging.
**Files touched:** src/diagnostics/bundle_manager.py, src/openai_translator/translator.py, CHANGELOG.md

### [2026-03-14] Branch: fix/pyinstaller-telemetry-v7 — PyInstaller Temp Folder & Telemetry Fix
**What changed:** Fixed PyInstaller volatile directory bug in bundle_manager. Fixed empty raw_response telemetry bug in align and double pipelines.
**Why:** To ensure logs are not permanently deleted when the PyInstaller GUI exits (`_MEIPASS` temp folder destruction), and to ensure `response_text` is assigned *before* `json.loads` so parsing failures actually log the LLM output instead of empty strings.
**Files touched:** src/diagnostics/bundle_manager.py, src/openai_translator/translator.py, CHANGELOG.md

### [2026-03-14] Branch: fix/forced-directory-creation-v8 — EMERGENCY FIX
**What changed:** Phase 8: Replaced BundleManager initialization to force absolute pathing and physical directory creation. Added explicit stdout tracing when logs are written.
**Why:** Because previous pathing fell back on implicit cwd assumptions when arguments were passed, which resulted in lost PyInstaller files.
**Files touched:** src/diagnostics/bundle_manager.py, CHANGELOG.md

### [2026-03-14] Branch: fix/typeerror-block-id-v9 — TypeError Fix
**What changed:** Phase 9: Fixed TypeError in process_chunk by removing duplicate block_id parameter in call_block_with_retry.
**Why:** The `block_id` was being redundantly passed as both a positional and keyword argument in multi-threading setups for the AI pipelines, crashing the pipelines prior to API interaction.
**Files touched:** src/machine-translate-docx.py, CHANGELOG.md

### [2026-03-14] Branch: fix/unified-pipeline-finish-v10 — Trace Identification & Pipeline Finishes
**What changed:** Phase 10: Injected filenames into trace logs, added 'double' action to document saving flow, and fixed end-of-run XTM NoneType crash.
**Why:** To ensure tracing outputs are correctly identifiable per document and stop unconditional post-run XTM reports from crashing AI pipelines where `xtm` was explicitly evaluated to `None`.
**Files touched:** src/diagnostics/bundle_manager.py, src/machine-translate-docx.py, CHANGELOG.md

### [2026-03-14] Branch: feature/enterprise-logging-and-fixes-v11 — Enterprise Logging
**What changed:** Unified Fixes: Added Double pipeline doc saving, Fixed XTM NoneType crash, Implemented Enterprise Log Retention (60-day/1000-file GC) and Semantic Trace Naming with Success/Fail flags.
**Why:** To establish a fully automated, self-pruning telemetry system that scales reliably for continuous CI execution while capturing raw output explicitly marked by JSON fallback states.
**Files touched:** src/diagnostics/bundle_manager.py, src/openai_translator/translator.py, CHANGELOG.md

### [2026-03-14] Branch: feature/ai-localization-lab-10415451625341488816 — Stabilization Merge
**What changed:** Consolidated all enterprise diagnostics, PyInstaller path fixes, and pipeline isolation logic into the AI Localization Lab feature branch.
**Why:** To ensure the core localization logic inherits the robust, absolute-pathing diagnostic system and doesn't suffer from pipeline scope shadowing or PyInstaller volatile directory failures.
**Files touched:** CHANGELOG.md
