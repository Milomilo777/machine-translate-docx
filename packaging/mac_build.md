# Building `mtd` for macOS

This document is the macOS counterpart of `packaging/README.md`.

> **Heads up — not yet validated.** The Windows .exe was built and
> end-to-end tested on 2026-05-14 (FA + FR with `gpt-5.4-mini`). The
> macOS instructions below are derived from the spec file's
> platform-aware behaviour and PyInstaller's documented Mac support,
> but I do not have a Mac available to confirm the steps run cleanly.
> Treat the first Mac build as a verification pass — open issues for
> anything that breaks and we'll fold the fix back into this file.

## Why PyInstaller can't cross-compile

PyInstaller bundles the **host** Python interpreter and the **host**
binary wheels. You cannot run PyInstaller on Windows and get a Mac
binary out the other end. The build must run on a real Mac (Intel or
Apple Silicon — match the chip you want to ship for).

If the team only has Windows boxes, an Apple Silicon Mac mini or
a cloud-hosted MacStadium instance is the cleanest path.

## Prerequisites

Tested target: macOS 13 (Ventura) or later, Apple Silicon. Intel x86_64
Macs also work but produce a separate binary that won't run on Apple
Silicon natively (and vice versa) unless you build a universal2
binary.

```bash
# 1. Install Python 3.11 — pyenv is the simplest path
brew install pyenv
pyenv install 3.11.7
pyenv shell 3.11.7
python --version    # → Python 3.11.7
```

## Clean build venv

Same logic as the Windows side: a system Python contaminated by
PyTorch / numpy / scipy will balloon the build to over a gigabyte.

```bash
cd machine-translate-docx-main
python -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip wheel setuptools

# Same runtime deps as Windows — pywin32 is intentionally omitted;
# cli.py only imports it under `if platform.system() == 'Windows'`.
pip install \
    pyinstaller \
    openai python-docx lxml requests certifi httpx tiktoken \
    openpyxl beautifulsoup4 json5 regex pyyaml \
    python-bidi chardet clipboard langcodes progressbar2 \
    psutil screeninfo selenium \
    newmm-tokenizer tinysegmenter
```

## Build

```bash
python -m PyInstaller packaging/mtd.spec --clean --noconfirm
```

Output:

```
dist/mtd/
├── mtd          ← the Mach-O executable (no extension)
└── _internal/   ← bundled python + libs + prompts/
```

The spec file detects `sys.platform == "darwin"` and:
  - skips `pywin32` / `win32com` / `pythoncom` / `pywintypes` hidden imports
  - skips the `.ico` icon (Mac uses `.icns`; none bundled yet)

## Smoke test

```bash
./dist/mtd/mtd --help
```

If you see the full argparse help, the import graph is clean. If you
see `dyld: Library not loaded …`, see "Common pitfalls" below.

## Real-world test

```bash
export OPENAI_API_KEY=sk-...
cd /path/to/some/input/dir
/path/to/dist/mtd/mtd \
  --docxfile input.docx \
  --destlang fa \
  --engine chatgpt \
  --enginemethod api \
  --aimodel gpt-5.4-mini \
  --with-polish \
  --silent \
  --exitonsuccess
```

The output `_PER_Polish.docx` lands next to `input.docx`. The sidecar
JSON lands in `Log json file/` next to `mtd`.

## Distribution to a teammate's Mac

### Path A — zip the folder (simplest, no signing)

```bash
cd dist
zip -r mtd-mac.zip mtd
```

End user:

```bash
unzip mtd-mac.zip
# macOS will quarantine downloaded zip contents — strip the flag:
xattr -dr com.apple.quarantine mtd
./mtd/mtd --help
```

Without the `xattr -dr` step Gatekeeper will block the unsigned
binary with "Apple cannot check this for malicious software." This
is the single most common reason a "build that worked locally" fails
on another Mac. The bigger your audience, the more sense codesign
makes.

### Path B — codesign + notarize (production)

Requires an Apple Developer account ($99/yr) and `xcrun notarytool`.

```bash
# 1. Sign every Mach-O binary in the bundle
codesign --deep --force --options=runtime \
  --sign "Developer ID Application: YOUR NAME (TEAMID)" \
  dist/mtd

# 2. Wrap in a .dmg or .zip
ditto -c -k --sequesterRsrc --keepParent dist/mtd mtd-mac.zip

# 3. Submit to Apple's notary service
xcrun notarytool submit mtd-mac.zip \
  --apple-id you@example.com \
  --team-id TEAMID \
  --password "@keychain:NOTARY_PASSWORD" \
  --wait

# 4. Staple the notarization ticket so it works offline
xcrun stapler staple dist/mtd
```

After this, end users can download and run with no quarantine fuss.

### Path C — .app bundle (graphical launcher feel)

If a future iteration wants a double-clickable `.app`, change
`exe = EXE(...)` in the spec to `console=False` and add a `BUNDLE()`
call at the end. PyInstaller's docs walk through this. Not done now
because the current build is CLI-only.

## Common pitfalls on macOS

| Symptom | Cause | Fix |
|---|---|---|
| `xcrun: error: invalid active developer path` | Xcode CLT missing | `xcode-select --install` |
| `"mtd" cannot be opened because the developer cannot be verified` | Quarantine attribute on a downloaded zip | `xattr -dr com.apple.quarantine ./mtd` |
| `Failed to load Python shared library` | Built against a python3.11 framework that's not present at runtime | Use the same python3.11 (pyenv or python.org installer) on the build + target Mac, or codesign with `--options=runtime` |
| `dyld: Library not loaded: @rpath/libssl.dylib` | OpenSSL pulled from Homebrew, target Mac doesn't have it at the same path | Build inside the clean venv with python.org installer (carries its own OpenSSL) or set `--target-arch=universal2` with bundled libs |
| Apple Silicon build won't run on Intel Mac | Different architecture | Build twice (one per arch) or use `--target-arch=universal2` with python.org's universal installer |
| `ModuleNotFoundError: No module named 'X'` at runtime | The clean venv was missing X; PyInstaller's static analyzer didn't flag it because cli.py's import was under a conditional | Add X to the `hiddenimports` list in `mtd.spec` |
| Chrome-related errors when running `--engine google` | The .exe builds the OpenAI-API path. Selenium engines need Chrome + chromedriver on the user's Mac | Document that .app/.exe builds support OpenAI API only |

## What's intentionally NOT in the spec

  - **pywin32 / win32com / pythoncom / pywintypes** — Windows-only,
    skipped on Mac. cli.py guards the runtime usage.
  - **The .ico icon** — wrong format for Mac. To add a real Mac icon:
    convert a 1024×1024 PNG to `.icns` with
    `iconutil -c icns google_translate.iconset/` (after creating the
    iconset folder per Apple's docs) and add it to the spec.

## Comparison with the Windows build

|  | Windows | Mac |
|---|---|---|
| Output | `dist/mtd/mtd.exe` | `dist/mtd/mtd` |
| Size | ~65 MB | ~70-80 MB (heavier libpython) |
| Signing | optional, SmartScreen friendly | strongly recommended (Gatekeeper) |
| Distribution | zip the folder | zip + xattr strip, or .dmg + codesign |
| Validated? | YES — 2026-05-14 (FA + FR) | **NOT YET** |
