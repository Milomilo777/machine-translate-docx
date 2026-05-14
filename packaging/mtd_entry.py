"""PyInstaller entry point for the `mtd` CLI executable.

Why a wrapper instead of pointing PyInstaller straight at
`machine_translate_docx.cli`:
  - PyInstaller's analysis is more reliable when it starts from a flat
    script. Module-style `-m machine_translate_docx.cli` collection
    sometimes misses sub-packages.
  - The wrapper is the single place to (a) freeze sys.path tweaks,
    (b) read frozen-mode env hints, (c) dispatch to the launcher
    sub-mode in a future iteration without rebuilding the spec.

The wrapper imports and calls ``machine_translate_docx.cli.main()``.
All argparse handling stays inside the CLI module — this script only
sets up the runtime.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_frozen_paths() -> None:
    """When running inside a PyInstaller bundle, set MTD_FROZEN_ROOT so
    downstream helpers (`log_paths.resolve_log_dir`, prompts finder)
    can pick a sensible on-disk location for runtime artefacts.

    - `sys._MEIPASS` (PyInstaller's temp extraction dir) holds the
      bundled `prompts/` directory; the existing finder walks up from
      package __file__ and lands there automatically.
    - For *writable* state (Log json file/ folder, sidecars), we use
      the executable's parent directory — that is the folder the end
      user sees, and it survives across runs (sys._MEIPASS is wiped on
      every exit).
    """
    if getattr(sys, "frozen", False):
        # PyInstaller sets sys.frozen=True and sys.executable to the .exe.
        exe_dir = Path(sys.executable).resolve().parent
        os.environ.setdefault("MTD_FROZEN_ROOT", str(exe_dir))


def main() -> int:
    _bootstrap_frozen_paths()
    # Import lazily so the bootstrap runs first.
    from machine_translate_docx.cli import main as cli_main
    return cli_main() or 0


if __name__ == "__main__":
    sys.exit(main())
