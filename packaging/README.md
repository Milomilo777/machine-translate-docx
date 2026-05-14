# Building a Standalone `mtd.exe` (Windows)

This folder holds the PyInstaller spec + wrapper that builds a
self-contained Windows executable for the OpenAI-API translation
flow. End users don't need Python, pip, or a clone of the repo —
they get a folder with `mtd.exe` and a `_internal/` subfolder, and
that's it.

## What's in the build

- `mtd_entry.py` — the small Python entry point PyInstaller runs.
  Sets `MTD_FROZEN_ROOT` so log paths and the prompts directory
  resolve next to the executable.
- `mtd.spec` — PyInstaller spec. Onedir mode. Bundles `prompts/`,
  `python-docx` data, `tiktoken` BPE files, and the Thai tokenizer
  data needed by the optional xlsx replacement memory.

## One-time build setup

PyInstaller picks up everything in the active Python's site-packages,
so use a **clean venv** to avoid hauling in PyTorch / PyQt5 / numpy /
scipy / matplotlib that have nothing to do with this CLI:

```bash
# from the repo root
python -m venv .venv-build
.venv-build/Scripts/python.exe -m pip install --upgrade pip wheel setuptools
.venv-build/Scripts/python.exe -m pip install \
    pyinstaller \
    openai python-docx lxml requests certifi httpx tiktoken \
    openpyxl beautifulsoup4 json5 regex pyyaml \
    python-bidi chardet clipboard langcodes progressbar2 \
    psutil screeninfo selenium pywin32 \
    newmm-tokenizer tinysegmenter
```

A bloated system Python turns a 65 MB build into a 1.2 GB build. The
clean venv keeps `dist/mtd/` at roughly 65 MB.

## Build

```bash
.venv-build/Scripts/python.exe -m PyInstaller packaging/mtd.spec --clean --noconfirm
```

Output: `dist/mtd/` (zip it; ship it). The folder is self-contained.

## Smoke test

```bash
dist/mtd/mtd.exe --help
```

Should print the full argparse help without a traceback.

## Real-world test

```bash
# from a directory holding an input .docx
mtd.exe \
  --docxfile input.docx \
  --destlang fa \
  --engine chatgpt \
  --enginemethod api \
  --aimodel gpt-5.4-mini \
  --with-polish \
  --silent \
  --exitonsuccess
```

The `OPENAI_API_KEY` env var must be set in the shell that runs
`mtd.exe`. The `prompts/` directory is bundled inside the .exe; the
output `_PER_Polish.docx` lands next to the input docx, and the
sidecar JSON lands under `Log json file/` next to `mtd.exe`.

A drop-in `prompts/` folder next to `mtd.exe` overrides the bundled
prompts (useful for testing custom prompt edits without rebuilding).

## What does NOT work in the packaged build

- **Google / DeepL engines** — they need a real Chrome install on the
  end user's machine plus matching `chromedriver`. Out of scope for a
  zero-install distribution. The CLI accepts `--engine google` but
  will fail at the WebDriver launch.
- **Local launcher / web UI** — only the CLI is packaged. The web
  launcher needs HTML templates + the v2 SPA bundled differently;
  that's a separate spec file (future work).

## Validation history

- 2026-05-13 Windows 10/11 — `gpt-5.4-mini` × `UL 3147` → French
  (94 s, $0.26), `VEGC 3148` → Persian (22 s, $0.07). Both produced
  native-quality output. See `CHANGELOG.md`.
