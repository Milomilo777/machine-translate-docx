"""Shared pytest configuration: make the in-repo `src/` package importable.

We do not install the project as a package; tests therefore prepend the
project's `src/` directory to `sys.path` so `import openai_tools.*` works.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
