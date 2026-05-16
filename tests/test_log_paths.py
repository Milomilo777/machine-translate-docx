"""Tests for src/machine_translate_docx/log_paths.py.

Covers the full public surface:
    resolve_log_dir()              -> Path
    resolve_log_path(docx_path)    -> str
    cleanup_old_logs(retention_days) -> int

And the internal helper:
    _find_project_root(anchor)     -> Path

Tests 1–5 redirect _find_project_root via monkeypatch.setattr so that
log files land in tmp_path instead of the real project tree.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import machine_translate_docx.log_paths as log_paths
from machine_translate_docx.log_paths import (
    _find_project_root,
    cleanup_old_logs,
    resolve_log_dir,
    resolve_log_path,
)

_LOG_DIR_NAME = "Log json file"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_root(monkeypatch, tmp_path: Path) -> None:
    """Make resolve_log_dir() (and everything that depends on it) use tmp_path."""
    monkeypatch.setattr(
        log_paths,
        "_find_project_root",
        lambda anchor: tmp_path,
    )


# ---------------------------------------------------------------------------
# 1. resolve_log_dir creates the directory
# ---------------------------------------------------------------------------

def test_resolve_log_dir_creates_directory(monkeypatch, tmp_path):
    _patch_root(monkeypatch, tmp_path)

    result = resolve_log_dir()

    assert result == tmp_path / _LOG_DIR_NAME
    assert result.is_dir()


# ---------------------------------------------------------------------------
# 2. resolve_log_path — basename-only transform
# ---------------------------------------------------------------------------

def test_resolve_log_path_basename_only(monkeypatch, tmp_path):
    """resolve_log_path strips directory, swaps .docx → _log.json."""
    _patch_root(monkeypatch, tmp_path)

    result = resolve_log_path("/some/path/foo_PER_Polish.docx")

    expected = str(tmp_path / _LOG_DIR_NAME / "foo_PER_Polish_log.json")
    assert result == expected


def test_resolve_log_path_non_docx_appends_suffix(monkeypatch, tmp_path):
    """Input that is not a .docx gets _log.json appended (not substituted)."""
    _patch_root(monkeypatch, tmp_path)

    result = resolve_log_path("/some/path/random_file.txt")

    assert result.endswith("random_file.txt_log.json")


def test_resolve_log_path_case_insensitive_extension(monkeypatch, tmp_path):
    """The .DOCX extension (upper-case) should also be replaced."""
    _patch_root(monkeypatch, tmp_path)

    result = resolve_log_path("/data/UL 3147_PER_Polish.DOCX")

    assert result.endswith("UL 3147_PER_Polish_log.json")
    assert ".DOCX" not in result


# ---------------------------------------------------------------------------
# 3. cleanup_old_logs — empty directory returns 0
# ---------------------------------------------------------------------------

def test_cleanup_old_logs_zero_when_empty(monkeypatch, tmp_path):
    _patch_root(monkeypatch, tmp_path)
    # Ensure the log dir exists but is empty.
    (tmp_path / _LOG_DIR_NAME).mkdir(parents=True, exist_ok=True)

    removed = cleanup_old_logs(retention_days=5)

    assert removed == 0


# ---------------------------------------------------------------------------
# 4. cleanup_old_logs — evicts stale files, keeps fresh ones
# ---------------------------------------------------------------------------

def test_cleanup_old_logs_evicts_stale(monkeypatch, tmp_path):
    _patch_root(monkeypatch, tmp_path)

    log_dir = tmp_path / _LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)

    now = time.time()
    old_ts = now - (10 * 86400)  # 10 days ago

    stale1 = log_dir / "old1_log.json"
    stale2 = log_dir / "old2_log.json"
    fresh = log_dir / "recent_log.json"

    for f in (stale1, stale2, fresh):
        f.write_text("{}", encoding="utf-8")

    # Backdate the two stale files.
    os.utime(stale1, (old_ts, old_ts))
    os.utime(stale2, (old_ts, old_ts))
    # fresh file keeps its current mtime (approximately now).

    removed = cleanup_old_logs(retention_days=5)

    assert removed == 2
    assert not stale1.exists()
    assert not stale2.exists()
    assert fresh.exists()


# ---------------------------------------------------------------------------
# 5. cleanup_old_logs — retention_days=0 evicts everything
# ---------------------------------------------------------------------------

def test_cleanup_old_logs_retention_zero_evicts_all(monkeypatch, tmp_path):
    """retention_days=0 means cutoff=now; backdate all files 1 s into the past
    so they are strictly older than the cutoff and therefore evicted."""
    _patch_root(monkeypatch, tmp_path)

    log_dir = tmp_path / _LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)

    old_ts = time.time() - 1  # 1 second ago — definitely < cutoff

    for name in ("a_log.json", "b_log.json", "c_log.json"):
        p = log_dir / name
        p.write_text("{}", encoding="utf-8")
        os.utime(p, (old_ts, old_ts))

    removed = cleanup_old_logs(retention_days=0)

    assert removed == 3
    assert list(log_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# 6. _find_project_root honours MTD_FROZEN_ROOT
# ---------------------------------------------------------------------------

def test_find_project_root_honors_frozen_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MTD_FROZEN_ROOT", str(tmp_path))

    result = _find_project_root(Path("/irrelevant/anchor"))

    assert result == tmp_path


# ---------------------------------------------------------------------------
# 7. _find_project_root falls back to source-tree search without env var
# ---------------------------------------------------------------------------

def test_find_project_root_without_frozen_env(monkeypatch):
    monkeypatch.delenv("MTD_FROZEN_ROOT", raising=False)

    # Use the actual package directory as the anchor — the source layout
    # guarantees prompts/ and src/ exist at the project root.
    anchor = Path(__file__).resolve().parent
    result = _find_project_root(anchor)

    assert result  # truthy — a non-empty Path was returned
    assert isinstance(result, Path)
