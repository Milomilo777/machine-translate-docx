# ADR 006: Phase B Architecture and Audit Notes

## Context
The repository is a hybrid Python + Java codebase. The Python desktop GUI builds CLI commands and depends on exact stdout and file-path contracts. The legacy Python translator remains present and supported. The Java CLI runner is compatibility-critical glue rather than an isolated interface. The Java web controller is a separate server entry point. Anti-bot rules in `AI_INSTRUCTIONS.md` require sequential web-engine execution. Tests currently cover CLI, controller, end-to-end flow, property tests, and architecture rules, but some coverage still depends on weak mocks.

## Decision
1. All migration work must preserve Python subprocess compatibility first.
2. CLI parsing must remain tolerant of Python-only flags and legacy engine names.
3. Web-engine concurrency controls are mandatory compliance, not optional optimisation.
4. Controller success tests must create real output artefacts when controller logic checks filesystem state.
5. Future migration ADRs must distinguish between primary Python desktop UI, Java backend, and server web UI.
