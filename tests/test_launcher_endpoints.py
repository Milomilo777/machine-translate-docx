"""Regression tests for local_launcher.py — cache helpers + /subscribe.

These pin the new endpoints introduced in commit 9a4d533 (v2-frontend feat):
  - _cache_key:        deterministic sha256 over payload + lang + engine + model
  - LocalState.cache_lookup / cache_store / _evict / cleanup_stale_cache
  - _append_subscriber: idempotent line-delimited writes to subscribers.txt

No HTTP, no subprocess, no OpenAI calls. Pure unit tests against module-level
helpers and the LocalState class with monkeypatched paths.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

import local_launcher
from local_launcher import (
    CACHE_TTL_SEC,
    LocalState,
    _append_subscriber,
    _cache_key,
    _double_lines_output_path,
    _engine_suffix_for,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_state(tmp_path: Path) -> LocalState:
    """Build a LocalState rooted at tmp_path with mock backend.

    Booting creates uploads/ logs/ views/ ssl/ cache/ subdirs and writes
    placeholder SSL certs — all under tmp_path so the test is hermetic.
    """
    state = LocalState(
        runtime_dir=tmp_path,
        backend_mode="mock",
        python_exe=Path("python"),
        script_path=tmp_path / "fake-script.py",
    )
    state.boot()
    return state


def _write_dummy(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ── _cache_key ───────────────────────────────────────────────────────────────

def test_cache_key_deterministic():
    payload = b"hello world" * 100
    k1 = _cache_key(payload, "fa", "chatgpt-polish", "gpt-5.5")
    k2 = _cache_key(payload, "fa", "chatgpt-polish", "gpt-5.5")
    assert k1 == k2
    assert len(k1) == 64  # sha256 hex


def test_cache_key_diverges_on_byte_flip():
    p1 = b"hello world"
    p2 = b"hello worle"  # one byte changed
    k1 = _cache_key(p1, "fa", "chatgpt", "gpt-5.5")
    k2 = _cache_key(p2, "fa", "chatgpt", "gpt-5.5")
    assert k1 != k2


def test_cache_key_diverges_on_lang_engine_model():
    payload = b"identical payload bytes"
    k_lang   = _cache_key(payload, "ar", "chatgpt", "gpt-5.5")
    k_engine = _cache_key(payload, "fa", "chatgpt-polish", "gpt-5.5")
    k_model  = _cache_key(payload, "fa", "chatgpt", "gpt-5.4-mini")
    base     = _cache_key(payload, "fa", "chatgpt", "gpt-5.5")
    assert len({base, k_lang, k_engine, k_model}) == 4


def test_cache_key_handles_none_model():
    # Real call sites may pass ai_model=None — must not crash and must
    # differ from the empty-string variant only by being equal to it
    # (both encode as b"" per current implementation).
    k_none  = _cache_key(b"x", "fa", "chatgpt", None)
    k_empty = _cache_key(b"x", "fa", "chatgpt", "")
    assert k_none == k_empty  # documented behaviour: None coerces to ""


# ── LocalState.cache_lookup / cache_store ────────────────────────────────────

def test_cache_lookup_returns_none_when_missing(tmp_path):
    state = _make_state(tmp_path)
    assert state.cache_lookup("nonexistent-key") is None


def test_cache_lookup_evicts_stale_entry(tmp_path, monkeypatch):
    state = _make_state(tmp_path)
    main = _write_dummy(state.uploads_dir / "main.docx", b"main")
    state.cache_store("k1", main_path=main)
    assert "k1" in state.cache

    # Rewind the entry's timestamp past the TTL.
    ts, data = state.cache["k1"]
    state.cache["k1"] = (ts - CACHE_TTL_SEC - 60, data)

    assert state.cache_lookup("k1") is None
    assert "k1" not in state.cache  # purged on access


def test_cache_lookup_evicts_when_paths_disappeared(tmp_path):
    state = _make_state(tmp_path)
    main = _write_dummy(state.uploads_dir / "main.docx", b"main")
    state.cache_store("k2", main_path=main)
    assert "k2" in state.cache

    # Simulate disk loss — delete the cached main copy.
    cached_copy = state.cache_dir / "k2" / "main.docx"
    assert cached_copy.exists()
    cached_copy.unlink()

    assert state.cache_lookup("k2") is None
    assert "k2" not in state.cache


def test_cache_lookup_evicts_pre_phase4_tuple_shape(tmp_path):
    """Old (timestamp, list-of-tuples) entries from a previous launcher
    must not crash the new lookup; they get evicted on access."""
    state = _make_state(tmp_path)
    legacy_path = _write_dummy(state.uploads_dir / "legacy.docx", b"x")
    # Inject a legacy-shape entry directly to simulate a stale cache from
    # a prior launcher version.
    state.cache["legacy-key"] = (time.time(), [("main", legacy_path)])

    assert state.cache_lookup("legacy-key") is None
    assert "legacy-key" not in state.cache


def test_cache_store_copies_files_into_cache_dir(tmp_path):
    state = _make_state(tmp_path)
    main   = _write_dummy(state.uploads_dir / "alpha_PER_TranslatePolish.docx", b"main-bytes")
    source = _write_dummy(state.uploads_dir / "alpha.docx",                     b"source-bytes")

    state.cache_store(
        "k3",
        main_path=main,
        source_file=source,
        engine="chatgpt-polish",
        ai_model="gpt-5.4-mini",
        src_lang="en",
        dest_lang="fa",
    )

    entry_dir = state.cache_dir / "k3"
    assert entry_dir.is_dir()
    assert (entry_dir / "alpha_PER_TranslatePolish.docx").read_bytes() == b"main-bytes"
    assert (entry_dir / "_source.docx").read_bytes() == b"source-bytes"

    _, data = state.cache["k3"]
    assert data["main_path"] == entry_dir / "alpha_PER_TranslatePolish.docx"
    assert data["source_path"] == entry_dir / "_source.docx"
    assert data["engine"] == "chatgpt-polish"
    assert data["dest_lang"] == "fa"


def test_cache_store_skips_when_main_missing(tmp_path):
    """If main_path does not exist on disk, cache_store is a no-op."""
    state = _make_state(tmp_path)
    ghost = state.uploads_dir / "ghost.docx"  # never created
    state.cache_store("k4", main_path=ghost)
    assert "k4" not in state.cache


def test_cache_store_persists_translation_arrays(tmp_path):
    """Phase 4: the cache value carries translation_array +
    phrase_separator_table so a different splitter can be applied later."""
    state = _make_state(tmp_path)
    main = _write_dummy(state.uploads_dir / "main.docx", b"m")
    state.cache_store(
        "k-data",
        main_path=main,
        translation_array=["hello", "world"],
        phrase_separator_table=["S1", "S2"],
        engine="chatgpt",
    )
    data = state.cache_lookup("k-data")
    assert data is not None
    assert data["translation_array"] == ["hello", "world"]
    assert data["phrase_separator_table"] == ["S1", "S2"]


def test_cleanup_stale_cache_evicts_old_entries(tmp_path):
    state = _make_state(tmp_path)
    fresh = _write_dummy(state.uploads_dir / "fresh.docx", b"f")
    stale = _write_dummy(state.uploads_dir / "stale.docx", b"s")
    state.cache_store("fresh-key", main_path=fresh)
    state.cache_store("stale-key", main_path=stale)

    # Age out only stale-key.
    ts, data = state.cache["stale-key"]
    state.cache["stale-key"] = (ts - CACHE_TTL_SEC - 1, data)

    evicted = state.cleanup_stale_cache()
    assert evicted == 1
    assert "fresh-key" in state.cache
    assert "stale-key" not in state.cache
    assert not (state.cache_dir / "stale-key").exists()


# ── filename helpers (phase 5 / phase 6) ─────────────────────────────────────

def test_engine_suffix_for_known_engines():
    assert _engine_suffix_for("google")          == "_Google"
    assert _engine_suffix_for("deepl")           == "_Deepl"
    assert _engine_suffix_for("chatgpt")         == "_chatGPT"
    assert _engine_suffix_for("chatgpt-polish")  == "_Polish"
    assert _engine_suffix_for("chatgpt-web")     == "_web_chatGPT"
    assert _engine_suffix_for("perplexity-web")  == "_web_Perplexity"


def test_engine_suffix_for_unknown_or_missing():
    assert _engine_suffix_for("yandex") == ""
    assert _engine_suffix_for(None)     == ""
    assert _engine_suffix_for("")       == ""
    assert _engine_suffix_for("  GOOGLE  ") == "_Google"  # trim + case


def test_double_lines_output_path_appends_before_extension():
    p = Path("/tmp/sample_PER_Polish.docx")
    assert _double_lines_output_path(p).name == "sample_PER_Polish_Double_Lines.docx"
    assert _double_lines_output_path(p).parent == p.parent

    p2 = Path("foo.DOCX")  # case-insensitive .docx removal
    assert _double_lines_output_path(p2).name == "foo_Double_Lines.docx"

    # Stems with no engine suffix still get _Double_Lines.
    p3 = Path("plain.docx")
    assert _double_lines_output_path(p3).name == "plain_Double_Lines.docx"


# ── _append_subscriber ───────────────────────────────────────────────────────

def test_subscribe_valid_email_appends(tmp_path, monkeypatch):
    sub_file = tmp_path / "subscribers.txt"
    monkeypatch.setattr(local_launcher, "SUBSCRIBERS_FILE", sub_file)

    ok, msg = _append_subscriber("alice@example.com")
    assert ok is True
    assert msg == "subscribed"
    assert sub_file.read_text(encoding="utf-8").splitlines() == ["alice@example.com"]


def test_subscribe_duplicate_is_idempotent(tmp_path, monkeypatch):
    sub_file = tmp_path / "subscribers.txt"
    monkeypatch.setattr(local_launcher, "SUBSCRIBERS_FILE", sub_file)

    ok1, _ = _append_subscriber("bob@example.com")
    ok2, msg2 = _append_subscriber("BOB@example.com")  # case-insensitive dedupe
    assert ok1 is True
    assert ok2 is True
    assert msg2 == "already subscribed"
    assert sub_file.read_text(encoding="utf-8").splitlines() == ["bob@example.com"]


def test_subscribe_rejects_bad_format(tmp_path, monkeypatch):
    sub_file = tmp_path / "subscribers.txt"
    monkeypatch.setattr(local_launcher, "SUBSCRIBERS_FILE", sub_file)

    for bad in ["not-an-email", "no@dot", "@nouser.com", "spaces in@it.com", ""]:
        ok, _ = _append_subscriber(bad)
        assert ok is False, f"should reject: {bad!r}"
    assert not sub_file.exists()  # nothing written


def test_subscribe_rejects_oversize(tmp_path, monkeypatch):
    sub_file = tmp_path / "subscribers.txt"
    monkeypatch.setattr(local_launcher, "SUBSCRIBERS_FILE", sub_file)

    long_local = "a" * 250
    huge = f"{long_local}@example.com"  # > 254 chars total
    assert len(huge) > 254
    ok, msg = _append_subscriber(huge)
    assert ok is False
    assert "long" in msg.lower()


def test_subscribe_strips_and_lowercases(tmp_path, monkeypatch):
    sub_file = tmp_path / "subscribers.txt"
    monkeypatch.setattr(local_launcher, "SUBSCRIBERS_FILE", sub_file)

    ok, _ = _append_subscriber("  Charlie@Example.COM  ")
    assert ok is True
    assert sub_file.read_text(encoding="utf-8").splitlines() == ["charlie@example.com"]
