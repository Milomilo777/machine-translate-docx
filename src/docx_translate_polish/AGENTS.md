# AGENTS.md - Docx Translate & Polish Module

This module provides an isolated, professional workflow for translating and polishing DOCX documents using the ChatGPT API.
It extracts and reorganizes the core AI translation logic from the legacy codebase into a clean, future-proof structure.

## Folder Map
- `core/`: Configuration, logging, and shared utilities (token estimation, cost calculation).
- `docx_io/`: Handlers for reading from and writing to DOCX files.
- `processing/`: Noise filtering and phrase/token chunking logic.
- `translation/`: AI prompt building, OpenAI client, and line splitting.
- `docs/`: Detailed architectural and workflow documentation.

## Key Rules
1. SENIOR ARCHITECT II review and explicit project owner approval required for all changes.
2. `translation/prompt_builder.py` is a PROTECTED file; do not modify without explicit written approval.
3. No new logic allowed during extraction, except for the deterministic `split_classic` mode.
4. All shared helpers (token estimation, cost calculation) must live only in `core/utils.py`.
5. Strictly adhere to hallucination prevention rules: ask if unclear, do not assume.

## Documentation
- [Architecture](docs/ARCHITECTURE.md)
- [Jules Role](docs/JULES_ROLE.md)
- [Workflow](docs/WORKFLOW.md)
- [Prompt Layers](docs/PROMPT_LAYERS.md)

Date: 2026-04-19
