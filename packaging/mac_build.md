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

### Path C — .app bundle (native Mac experience)

`packaging/mtd.spec` now includes a `BUNDLE(...)` call gated by
`IS_MACOS`. Building on a Mac produces both:

```
dist/mtd/         ← onedir folder (mtd binary + _internal/)
dist/mtd.app/     ← Mac app bundle (drag to Applications)
```

The `.app` is a wrapper around the same binary plus an `Info.plist`
with `CFBundleIdentifier=com.smtv.mtd`, `LSMinimumSystemVersion=10.13`,
and `NSHighResolutionCapable=true`. Bundle identifier is reverse-DNS
so codesign + notarisation can track it.

**Adding a Mac icon** (optional):

```bash
# 1. Source: any 1024×1024 PNG (transparent background recommended).
mkdir mtd.iconset
sips -z 16 16     icon.png --out mtd.iconset/icon_16x16.png
sips -z 32 32     icon.png --out mtd.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out mtd.iconset/icon_32x32.png
sips -z 64 64     icon.png --out mtd.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out mtd.iconset/icon_128x128.png
sips -z 256 256   icon.png --out mtd.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out mtd.iconset/icon_256x256.png
sips -z 512 512   icon.png --out mtd.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out mtd.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out mtd.iconset/icon_512x512@2x.png

# 2. Convert to .icns
iconutil -c icns mtd.iconset

# 3. Drop into packaging/ before building
mv mtd.icns packaging/mtd.icns
```

The spec auto-picks `packaging/mtd.icns` when present and skips it
quietly otherwise (no build break).

### Path D — .dmg disk image (the proper Mac distribution format)

Once you have a `.app`, wrap it in a `.dmg` so users get the canonical
"drag the icon to Applications" experience. Requires `create-dmg`
(Homebrew):

```bash
brew install create-dmg

# Drop the .app into a staging folder so the .dmg only contains it
mkdir -p dist/dmg-staging
cp -r "dist/mtd.app" dist/dmg-staging/

# If a previous .dmg exists, remove it first
rm -f "dist/Machine Translate DOCX.dmg"

create-dmg \
  --volname        "Machine Translate DOCX" \
  --volicon        packaging/mtd.icns \
  --window-pos     200 120 \
  --window-size    600 300 \
  --icon-size      100 \
  --icon           "mtd.app" 175 120 \
  --hide-extension "mtd.app" \
  --app-drop-link  425 120 \
  --no-mount \
  "dist/Machine Translate DOCX.dmg" \
  "dist/dmg-staging/"
```

The end user double-clicks the `.dmg`, drags `mtd.app` onto the
Applications shortcut, and launches from Spotlight/Launchpad. The
`--volicon` step gives the mounted volume itself a custom icon.

**Don't forget**: an unsigned `.dmg` is still subject to Gatekeeper
quarantine. The full polished flow is:

```bash
# 1. Sign the .app
codesign --deep --force --options=runtime \
  --sign "Developer ID Application: YOUR NAME (TEAMID)" \
  dist/mtd.app

# 2. Build the .dmg (as above)
# 3. Sign the .dmg itself
codesign --sign "Developer ID Application: YOUR NAME (TEAMID)" \
  "dist/Machine Translate DOCX.dmg"

# 4. Notarise
xcrun notarytool submit "dist/Machine Translate DOCX.dmg" \
  --apple-id you@example.com --team-id TEAMID \
  --password "@keychain:NOTARY_PASSWORD" --wait

# 5. Staple
xcrun stapler staple "dist/Machine Translate DOCX.dmg"
```

After step 5 the `.dmg` opens cleanly on any Mac, no quarantine fuss.

### Comparison with the upstream repo's Mac build

The upstream repo (`translation-robot/machine-translate-docx`) has a
Mac build in `compile/mac/MachineTranslator.spec` + `compileall.sh` +
`builddmg-gui.sh`. We borrowed the BUNDLE() and create-dmg patterns
from there. Where we diverged:

| Choice | Upstream | This repo |
|---|---|---|
| Heavy NLP deps (parsivar, gensim, sklearn, demoji, usaddress) | bundled | NOT bundled (lazy-loaded or removed) |
| upx compression | `upx=True` | `upx=False` (UPX-compressed Mach-O is rejected by Apple notarytool) |
| Python source | hardcoded `/Library/Frameworks/Python.framework/...` paths | clean venv chosen by the operator |
| Selenium binaries | bundled, then manually stripped | bundled but no chromedriver — the API path doesn't need it |
| Build artefacts | `Machine Translator Term.app` + GUI `Machine Translator.app` | `mtd.app` only (CLI) |
| .icns icon | bundled in repo | optional — drop your own at `packaging/mtd.icns` |
| Result size | ~300+ MB | ~70-80 MB |
| Cross-platform spec | separate Mac + Windows spec files | single platform-aware `mtd.spec` |

The smaller surface is the main win — fewer transitive deps mean
fewer reasons for a Mac build to break with a `dyld: Library not
loaded` after the user upgrades their system.

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
| `.app` bundle | n/a | optional via `BUNDLE()` in spec |
| `.dmg` distribution | n/a | optional via `create-dmg` |
| Icon | `google_translate.ico` | optional `packaging/mtd.icns` |
