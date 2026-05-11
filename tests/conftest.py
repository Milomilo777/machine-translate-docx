"""Shared pytest configuration: make the in-repo package importable.

The repository follows the standard `src/` layout — the actual
package lives at `src/machine_translate_docx/`. Tests prepend the
project's `src/` directory to `sys.path` so
`from machine_translate_docx.<module> import …` works without
requiring a prior `pip install -e .`.

This is the test-time equivalent of what `pip install -e .` would
do via `pyproject.toml`'s `[tool.setuptools]` layout.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# Project root holds local_launcher.py; tests for the launcher endpoints
# need to import it directly. Prepend after src/ so src/ wins for package names.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
