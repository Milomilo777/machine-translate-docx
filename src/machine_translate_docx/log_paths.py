"""Resolve and curate the central `Log json file/` folder.

2026-05-13: sidecar `_log.json` files used to land next to the output
docx. The user asked for them to land in a single project-root folder
named `Log json file/` with a 10-day retention sweep so old runs do not
accumulate forever.

Public surface:
    resolve_log_dir()             -> Path
    resolve_log_path(out_docx)    -> str (full path inside the folder)
    cleanup_old_logs(days=10)     -> int (files removed)
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

_LOG_DIR_NAME = "Log json file"
_RETENTION_DAYS = 10


def _find_project_root(anchor: Path) -> Path:
    """Walk up from *anchor* until we find a directory that contains
    both `prompts/` and `src/` — the project root signature."""
    for candidate in [anchor, *anchor.parents]:
        if (candidate / "prompts").is_dir() and (candidate / "src").is_dir():
            return candidate
    # Fallback: cwd. Better than crashing in a half-set-up env.
    return Path.cwd()


def resolve_log_dir() -> Path:
    """Return the central `Log json file/` directory, creating it if needed."""
    root = _find_project_root(Path(__file__).resolve().parent)
    log_dir = root / _LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def resolve_log_path(output_docx_path: str) -> str:
    """Map an output docx path to its sidecar path inside the central folder.

    e.g. `…/UL 3147_PER_Polish.docx` → `<root>/Log json file/UL 3147_PER_Polish_log.json`.
    """
    base = os.path.basename(output_docx_path)
    base = re.sub(r"(?i)\.docx$", "_log.json", base)
    # If the input wasn't a .docx, just append the suffix.
    if not base.endswith("_log.json"):
        base = f"{base}_log.json"
    return str(resolve_log_dir() / base)


def cleanup_old_logs(retention_days: int = _RETENTION_DAYS) -> int:
    """Delete `_log.json` files older than *retention_days*. Return count removed.

    Silent on individual failures: a sidecar that can't be deleted is logged
    to stderr but never raises.
    """
    cutoff = time.time() - (retention_days * 86400)
    removed = 0
    try:
        log_dir = resolve_log_dir()
    except Exception:
        return 0
    for path in log_dir.glob("*_log.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except Exception as exc:
            print(f"[WARN] log retention: could not delete {path.name}: {exc!r}")
    return removed
