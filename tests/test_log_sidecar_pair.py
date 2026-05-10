"""W-4 (2026-05-11) — log.json sidecar always travels with its docx.

The chatgpt-polish pipeline writes two files: ``foo_PER_Polish.docx``
and ``foo_PER_Polish_log.json``. The launcher's ``_strip_timestamp``
helper renames the docx if the upload prefix carries a millisecond
timestamp (e.g. ``1778036666789-foo.docx``); without W-8 the sidecar
was left under the old name and its ``run_info.output_file`` field
pointed at a docx that no longer existed.

These tests pin the contract:
  1. ``_strip_timestamp(docx_path)`` renames the sidecar alongside.
  2. After rename, the sidecar's ``run_info.output_file`` matches
     the post-rename docx name.

We only exercise the launcher's helper; the docx + sidecar are
plain temp files (no real translation needed).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_launcher  # noqa: E402  — sys.path tweak above


def _make_pair(tmp_path: Path, docx_name: str) -> tuple[Path, Path]:
    """Build a docx + log.json pair next to each other in tmp_path."""
    docx_path = tmp_path / docx_name
    docx_path.write_bytes(b"PK\x03\x04 fake docx body")
    sidecar_path = tmp_path / docx_name.replace(".docx", "_log.json")
    sidecar_path.write_text(
        json.dumps({
            "run_info": {"output_file": docx_name, "model": "gpt-5.4-mini"},
            "blocks":   [],
            "summary":  {"total_blocks": 0},
        }),
        encoding="utf-8",
    )
    return docx_path, sidecar_path


class _MiniHandler:
    """Just enough surface for ``_strip_timestamp`` to run.

    The real RequestHandler is overkill for this test — we only need
    the unbound method copied onto a stand-in class so we can call
    ``handler._strip_timestamp(path)`` without spinning up an HTTP
    server. The helper has no dependencies on the request / state
    machinery.
    """

    _strip_timestamp = local_launcher.MockTranslatorHandler._strip_timestamp


def test_strip_timestamp_renames_docx_only_when_no_sidecar(tmp_path):
    docx, _ = _make_pair(tmp_path, "1778036666789-foo.docx")
    sidecar = tmp_path / "1778036666789-foo_log.json"
    sidecar.unlink()  # ensure no sidecar
    handler = _MiniHandler()
    new_path = handler._strip_timestamp(docx)
    assert new_path.name == "foo.docx"
    assert new_path.exists()
    # Old name removed.
    assert not (tmp_path / "1778036666789-foo.docx").exists()


def test_strip_timestamp_renames_sidecar_alongside_docx(tmp_path):
    docx, sidecar = _make_pair(tmp_path, "1778036666789-foo.docx")
    handler = _MiniHandler()

    new_docx = handler._strip_timestamp(docx)

    # The docx was renamed.
    assert new_docx.name == "foo.docx"
    assert new_docx.exists()

    # The sidecar moved to the matching name.
    new_sidecar = tmp_path / "foo_log.json"
    assert new_sidecar.exists(), "sidecar was not renamed alongside docx"
    assert not sidecar.exists(), "old sidecar name still present"


def test_strip_timestamp_rewrites_output_file_field(tmp_path):
    docx, _ = _make_pair(tmp_path, "1778036666789-foo.docx")
    handler = _MiniHandler()

    new_docx = handler._strip_timestamp(docx)
    new_sidecar = tmp_path / "foo_log.json"
    payload = json.loads(new_sidecar.read_text(encoding="utf-8"))

    # The sidecar's output_file field was rewritten to match the
    # post-rename docx name (W-8 contract).
    assert payload["run_info"]["output_file"] == new_docx.name
    # Other fields untouched.
    assert payload["run_info"]["model"] == "gpt-5.4-mini"


def test_strip_timestamp_is_idempotent_when_no_prefix(tmp_path):
    """Files without a timestamp prefix should round-trip unchanged."""
    docx, sidecar = _make_pair(tmp_path, "regular.docx")
    handler = _MiniHandler()

    result = handler._strip_timestamp(docx)
    assert result == docx
    assert docx.exists()
    assert sidecar.exists()
