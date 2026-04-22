## Changelog — docx_translate_polish

### v0.4 — 2026-04-20
- CRITICAL FIX: Deleted src/gui_translate_polish.py (contained model= bug)
- CRITICAL FIX: Eliminated all TranslationConfig() calls with unsupported model= kwarg
- Added Language Configuration panel to GUI (source + destination dropdowns)
- All languages loaded from google_translate_lang_codes, sorted A-Z
- Persian set as default destination, English as default source
- Language selection persisted in settings file
- Splitting mode wiring verified end-to-end
- Log timestamps added in HH:MM:SS format
- Renamed internal module files for better clarity (openai_engine.py, chunker.py moved to translation/)

### v0.3 — 2026-04-19
- GUI moved to project root with correct sys.path bootstrap
- Fixed: TranslationConfig no longer receives unsupported model= argument
- Splitting mode (classic/ai) fully wired from GUI to pipeline.run()
- All languages loaded from backend config
- Dual persistence: state file + settings file
- Thread-safe worker with HH:MM:SS logging

### v0.2 — 2026-04-19
- AI splitting logic implemented in splitter.py
- OpenAI pricing tiers added to utils.py
- GUI wired to extracted module (initial attempt)
- AGENTS.md added

### v0.1 — 2026-04-19
- Initial extraction of OpenAI translation workflow from legacy code
- Module structure created: core, docx_io, processing, translation
- pipeline.py created as orchestrator
