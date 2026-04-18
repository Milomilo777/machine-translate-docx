# Architecture Documentation

## Purpose and Isolation Philosophy
The Docx Translate & Polish module is designed as an isolated component to decouple the AI translation workflow from the main monolithic script. This ensures better maintainability, testability, and portability of the translation logic.

## Data Flow Diagram
```
input.docx → reader → noise_filter → chunker
             → prompt_builder → openai_client
             → splitter → writer → output.docx
```

## Decision Log
- **2026-04-19**: Initial extraction of the OpenAI workflow into a dedicated module structure.
- **2026-04-19**: Unified shared utilities into `core/utils.py` to prevent logic duplication.
- **2026-04-19**: Implemented recursive block-splitting in `openai_client.py` for robust API handling.

## Changelog
- **v0.1.0**: Initial release - Extraction and reorganization of core translation logic.
