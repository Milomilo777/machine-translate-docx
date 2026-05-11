"""Unit tests for the Telegram alert helpers in ``local_launcher.py``.

The send-document code path makes a real HTTPS POST in production; here
we monkey-patch ``urllib.request.urlopen`` so the body and URL can be
inspected without touching the network. Token / chat_id values are
fake; the test only verifies the request shape and the body wiring.
"""
from __future__ import annotations

import json
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_launcher  # noqa: E402


# ── _telegram_escape ────────────────────────────────────────────────────


def test_escape_neutralises_markdown_specials():
    s = "my_doc*name.docx [v1] `back`tick \\back"
    out = local_launcher._telegram_escape(s)
    assert "\\_" in out
    assert "\\*" in out
    assert "\\[" in out
    assert "\\`" in out
    assert "\\\\" in out


def test_escape_passes_other_chars_through():
    src = "normal text · with em-dash — and digits 1234"
    assert local_launcher._telegram_escape(src) == src


def test_escape_handles_none_and_empty():
    assert local_launcher._telegram_escape(None) == ""
    assert local_launcher._telegram_escape("") == ""


# ── _telegram_send_document ─────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self): return self._body


def test_send_document_constructs_multipart(tmp_path):
    docx = tmp_path / "input.docx"
    docx.write_bytes(b"PK\x03\x04 not a real docx but binary")

    captured = {}
    def _fake_urlopen(req, timeout=None):
        captured["url"]  = req.full_url
        captured["body"] = req.data
        captured["hdr"]  = dict(req.headers)
        return _FakeResponse(b'{"ok":true,"result":{}}')

    with patch("urllib.request.urlopen", _fake_urlopen):
        local_launcher.MockTranslatorHandler._telegram_send_document(
            token="FAKE_TOKEN_123",
            chat_id="987654321",
            file_path=docx,
            caption="test cap",
        )

    assert "https://api.telegram.org/botFAKE_TOKEN_123/sendDocument" == captured["url"]
    # Header carries multipart boundary.
    ct = captured["hdr"].get("Content-type") or captured["hdr"].get("Content-Type")
    assert ct and ct.startswith("multipart/form-data; boundary=----mtd-")
    # Body contains chat_id field, caption, and the file bytes.
    body = captured["body"]
    assert b'name="chat_id"' in body
    assert b'987654321' in body
    assert b'name="caption"' in body
    assert b'test cap' in body
    assert b'name="document"; filename="input.docx"' in body
    assert b'PK\x03\x04 not a real docx but binary' in body


def test_send_document_raises_on_telegram_rejection(tmp_path):
    docx = tmp_path / "x.docx"
    docx.write_bytes(b"PK")
    def _fake_urlopen(req, timeout=None):
        return _FakeResponse(b'{"ok":false,"description":"chat not found"}')
    with patch("urllib.request.urlopen", _fake_urlopen):
        with pytest.raises(RuntimeError) as exc:
            local_launcher.MockTranslatorHandler._telegram_send_document(
                token="t", chat_id="c", file_path=docx, caption=""
            )
    assert "telegram rejected" in str(exc.value).lower()
