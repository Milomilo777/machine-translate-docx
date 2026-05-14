# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the `mtd` CLI executable.

Build (Windows):
    python -m PyInstaller packaging/mtd.spec --clean --noconfirm
    → dist/mtd/mtd.exe   (~65 MB onedir)

Build (macOS):
    python3 -m PyInstaller packaging/mtd.spec --clean --noconfirm
    → dist/mtd/mtd        (Unix binary, no extension)
    See packaging/mac_build.md for the full Mac flow (codesign,
    quarantine attribute, .dmg packaging).

Build (Linux): same as macOS; output is `dist/mtd/mtd`.

Why onedir, not onefile:
  - onefile re-extracts to a temp dir on every launch (~0.5-1s slow
    startup, broken antivirus signature on some systems, Gatekeeper
    headache on Mac).
  - onedir produces a folder the user can ship as-is. The binary +
    a `_internal/` directory sit side-by-side.
  - For network distribution: zip the folder, end user unzips, runs
    `mtd[.exe]`. No installer needed.

2026-05-14: spec is platform-aware. The Windows-only hidden imports
(pywin32, win32com, pythoncom, pywintypes) and the .ico icon are
gated by `sys.platform` so the same spec builds cleanly on Win + Mac
+ Linux. cli.py already wraps `from win32com.client import Dispatch`
in `if platform.system() == 'Windows'` so the runtime path is safe.
"""
import sys as _sys
from pathlib import Path

import PyInstaller.utils.hooks as _hooks

REPO_ROOT = Path(SPECPATH).parent.resolve()
IS_WINDOWS = _sys.platform.startswith("win")
IS_MACOS   = _sys.platform == "darwin"
IS_LINUX   = _sys.platform.startswith("linux")

# ── data files bundled inside the package ──────────────────────────────────
datas = [
    # Prompts directory — the translator + polisher load these at runtime.
    (str(REPO_ROOT / "prompts"), "prompts"),
]

# python-docx ships XML templates inside its package; PyInstaller catches
# these via its default hooks, but we collect explicitly to be safe.
datas += _hooks.collect_data_files("docx")
# tiktoken ships its BPE rank files as package data.
try:
    datas += _hooks.collect_data_files("tiktoken")
    datas += _hooks.collect_data_files("tiktoken_ext")
except Exception:
    pass
# newmm_tokenizer ships a Thai word list as package data; without it the
# tokenizer raises at import time.
try:
    datas += _hooks.collect_data_files("newmm_tokenizer")
except Exception:
    pass

# ── hidden imports ─────────────────────────────────────────────────────────
# PyInstaller's static analyzer follows `import` statements but misses:
#   - importlib-based dynamic imports (tiktoken's encoding registry)
#   - lazy plugin discovery (openai's transport selection)
#   - sub-packages of our own project that are only touched via attribute
#     access (machine_translate_docx.openai_tools.*).
hiddenimports = [
    # Our own sub-packages — explicit so the spec doesn't drift.
    "machine_translate_docx",
    "machine_translate_docx.cli",
    "machine_translate_docx.config",
    "machine_translate_docx.dispatch",
    "machine_translate_docx.exceptions",
    "machine_translate_docx.log_paths",
    "machine_translate_docx.runner",
    "machine_translate_docx.runtime",
    "machine_translate_docx.table",
    "machine_translate_docx.translation_health",
    "machine_translate_docx.docx_io",
    "machine_translate_docx.docx_io.parse",
    "machine_translate_docx.docx_io.cells",
    "machine_translate_docx.docx_io.runs",
    "machine_translate_docx.docx_io.save",
    "machine_translate_docx.docx_io.annotations",
    "machine_translate_docx.docx_io.get_cell_data",
    "machine_translate_docx.engines",
    "machine_translate_docx.engines.chatgpt_api",
    "machine_translate_docx.openai_tools",
    "machine_translate_docx.openai_tools.translator",
    "machine_translate_docx.openai_tools.polisher",
    "machine_translate_docx.openai_tools.persian_double_lines",
    "machine_translate_docx.openai_tools.splitting",
    "machine_translate_docx.openai_tools.fa_postprocess",
    "machine_translate_docx.openai_tools.line_count_reconciler",
    "machine_translate_docx.openai_tools._retry",
    "machine_translate_docx.openai_tools.aligner_per",
    "machine_translate_docx.xlsx_translation_memory",
    # Third-party
    "openai",
    "httpx",
    "httpcore",
    "tiktoken",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    "docx",
    "lxml",
    "lxml.etree",
    "lxml._elementpath",
    "openpyxl",
    "openpyxl.cell._writer",
    "bs4",
    "requests",
    "certifi",
    "json5",
    "regex",
    "yaml",
    # cli.py imports these unconditionally (top-level imports);
    # they MUST be bundled even though they only fire on non-OpenAI
    # paths in practice.
    "bidi",
    "bidi.algorithm",
    "chardet",
    "clipboard",
    "langcodes",
    "progressbar",
    "psutil",
    "screeninfo",
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.chrome",
    "selenium.webdriver.chrome.options",
    "selenium.webdriver.chrome.service",
    "selenium.webdriver.common.by",
    "selenium.webdriver.support",
    "selenium.webdriver.support.ui",
    "selenium.webdriver.support.expected_conditions",
    "selenium.webdriver.remote.remote_connection",
    "selenium.webdriver.common.action_chains",
    "selenium.webdriver.common.keys",
    "selenium.common.exceptions",
    # xlsx_translation_memory transitive deps
    "newmm_tokenizer",
    "newmm_tokenizer.tokenizer",
    "tinysegmenter",
]

# Windows-only hidden imports — pywin32 family. cli.py only imports
# win32com.client behind a `platform.system() == 'Windows'` guard, so on
# Mac / Linux these modules don't exist and PyInstaller must NOT try to
# bundle them.
if IS_WINDOWS:
    hiddenimports += [
        "win32com",
        "win32com.client",
        "pythoncom",
        "pywintypes",
    ]

# Collect all submodules of openai / httpx — they discover plugins via
# importlib at runtime.
hiddenimports += _hooks.collect_submodules("openai")
hiddenimports += _hooks.collect_submodules("httpx")
hiddenimports += _hooks.collect_submodules("tiktoken_ext")

# ── excludes (slim the binary) ──────────────────────────────────────────────
# Things we definitely don't ship as a CLI:
excludes = [
    "tkinter",          # GUI toolkit; we're CLI-only
    "matplotlib",       # plotting; not used
    "PIL",              # image processing; not used
    "webdriver_manager",
    # cli.py top-level imports selenium, so we MUST include selenium —
    # but the network-engine path is dormant when the user only runs
    # `--engine chatgpt --enginemethod api`. Just don't ship Chrome.
]

block_cipher = None

a = Analysis(
    [str(REPO_ROOT / "packaging" / "mtd_entry.py")],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mtd",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon: .ico is Windows-only. macOS would want a .icns file (none
    # bundled yet); on non-Windows we skip the icon rather than crash
    # PyInstaller with a wrong-format file.
    icon=(
        str(REPO_ROOT / "google_translate.ico")
        if IS_WINDOWS and (REPO_ROOT / "google_translate.ico").exists()
        else None
    ),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mtd",
)
