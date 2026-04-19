## docx_translate_polish

**Purpose:** Isolated, professional-grade DOCX translation module using OpenAI API.
**Status:** Active — GUI wired and tested.

### File Map

    machine-translate-docx/
    │
    ├── gui_translate_polish.py          ← GUI (project root — NOT inside src/)
    ├── gui_translate_polish_state.json  ← last DOCX/Dict (auto-generated)
    ├── translate_polish_settings.json   ← engine/lang/mode prefs (auto-generated)
    │
    └── src/
        └── docx_translate_polish/
            ├── __init__.py              ← public exports
            ├── pipeline.py             ← orchestrator: input → output
            ├── AGENTS.md               ← Jules instructions (do not edit manually)
            ├── requirements.txt
            ├── core/
            │   ├── config.py           ← TranslationConfig + language list
            │   └── utils.py            ← pricing tiers, shared helpers
            ├── docx_io/
            │   ├── reader.py           ← reads 3-column DOCX translation table
            │   └── writer.py           ← writes translation back with RTL/format
            ├── processing/
            │   └── noise_filter.py     ← removes decorative shading
            ├── translation/
            │   ├── chunker.py          ← splits text into token-safe API blocks
            │   ├── openai_engine.py    ← OpenAI calls, retry, cost tracking
            │   ├── prompt_builder.py   ← multi-layer reflective prompt builder
            │   └── splitter.py         ← line splitting: classic or ai mode
            └── docs/
                ├── README.md           ← this file
                └── CHANGELOG.md

### How to Run

1. Place project at local path
2. Set OPENAI_API_KEY in environment or enter in GUI
3. Run: `python gui_translate_polish.py`
4. Select DOCX file (3-column format: source | notes | translation)
5. Choose Translate Engine, Splitting Mode, Source/Destination language
6. Click **Translate (Raw)**
7. Output file appears next to input file

### Pipeline Flow

1. **Reader** → open DOCX, extract 3-column table rows
2. **NoiseFilter** → remove empty/decorative rows
3. **Chunker** → group rows into token-safe blocks
4. **Splitter** → split long source lines (classic or ai mode)
5. **OpenAI Engine** → send prompt, receive translation, retry on fail
6. **Writer** → write translation into column 3, preserve RTL + font

### Supported Models

| Display Name     | API ID         | Notes              |
|------------------|----------------|--------------------|
| ChatGPT 5.4      | gpt-5.4        | Default            |
| ChatGPT 5.4 Mini | gpt-5.4-mini   | Faster, lower cost |

### Splitting Modes

| Mode    | Description                                   |
|---------|-----------------------------------------------|
| classic | Rule-based split on punctuation and length    |
| ai      | OpenAI-powered intelligent split via prompt   |

### Future Roadmap (in GUI, not yet in backend)

- **Polish Engine**: post-translation polish pass via OpenAI
- **Reasoning Level**: medium / high / xhigh per model
- **Dictionary (XLSX)**: terminology override during translation
- **Splitting Engine selector**: choose which model runs the split

### Key Design Principles

- GUI is thin: zero business logic
- Module is fully isolated: no dependency on main.py or legacy code
- Future-ready: each stage is a separate file, easy to extend
- State persists: last file + settings auto-restored on GUI launch
