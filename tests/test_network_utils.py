"""Tests for machine_translate_docx.network_utils.

All tests are fully offline — no real network calls are made.
socket.socket and requests.get are monkeypatched per test.

Sprint B (2026-05-16): historical ``test_internet`` was renamed to
``probe_internet`` so pytest doesn't collect it as a non-None test
function. SSRF allowlist added — tests use ``ip-api.com``
(allowlisted by default) or extend the allowlist via
``MTD_NETWORK_ALLOW_HOSTS``.
"""
from __future__ import annotations

import json
import socket
from unittest.mock import MagicMock

import pytest
import requests

from machine_translate_docx.network_utils import (
    check_mirror_url,
    fetch_country_data,
    probe_internet,
    set_se_driver_mirror_url_if_needed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    """Build a minimal requests.Response mock."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status.return_value = None  # no-op by default
    return resp


def _allow_host(monkeypatch, host: str) -> None:
    """Extend the network_utils SSRF allowlist for one test."""
    monkeypatch.setenv("MTD_NETWORK_ALLOW_HOSTS", host)


# ---------------------------------------------------------------------------
# probe_internet
# ---------------------------------------------------------------------------

def test_probe_internet_success(monkeypatch):
    """TCP connect succeeds → True returned."""
    fake_sock = MagicMock()
    fake_sock.__enter__ = MagicMock(return_value=fake_sock)
    fake_sock.__exit__ = MagicMock(return_value=False)
    fake_sock.connect.return_value = None
    fake_sock.settimeout.return_value = None

    monkeypatch.setattr("socket.socket", lambda *a, **kw: fake_sock)
    assert probe_internet() is True


def test_probe_internet_failure(monkeypatch):
    """socket.error on connect → False returned."""
    def _make_failing_sock(*a, **kw):
        sock = MagicMock()
        sock.__enter__ = MagicMock(return_value=sock)
        sock.__exit__ = MagicMock(return_value=False)
        sock.settimeout.return_value = None
        sock.connect.side_effect = socket.error("nope")
        return sock

    monkeypatch.setattr("socket.socket", _make_failing_sock)
    assert probe_internet() is False


# ---------------------------------------------------------------------------
# fetch_country_data
# ---------------------------------------------------------------------------

def test_fetch_country_data_success(monkeypatch):
    """status==success with country field → returns the country string."""
    payload = {"status": "success", "country": "Australia"}
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(200, payload)
    )
    # ip-api.com is in the default allowlist
    result = fetch_country_data("http://ip-api.com/json/")
    assert result == "Australia"


def test_fetch_country_data_non_success_status(monkeypatch):
    """status!=success → returns None."""
    payload = {"status": "fail", "message": "private range"}
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(200, payload)
    )
    result = fetch_country_data("http://ip-api.com/json/")
    assert result is None


def test_fetch_country_data_request_exception(monkeypatch):
    """requests.get raises RequestException → returns None."""
    def _raise(*a, **kw):
        raise requests.exceptions.RequestException("network error")

    monkeypatch.setattr("requests.get", _raise)
    result = fetch_country_data("http://ip-api.com/json/")
    assert result is None


def test_fetch_country_data_json_decode_error(monkeypatch):
    """response.json() raises JSONDecodeError → returns None."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.side_effect = json.JSONDecodeError("bad json", "", 0)

    monkeypatch.setattr("requests.get", lambda *a, **kw: resp)
    result = fetch_country_data("http://ip-api.com/json/")
    assert result is None


def test_fetch_country_data_host_not_in_allowlist_skips_request(monkeypatch, capsys):
    """SSRF guard: hostname not in allowlist → return None, never call requests.get."""
    called = {"n": 0}

    def _track(*a, **kw):
        called["n"] += 1
        return _make_response(200, {"status": "success", "country": "Pwned"})

    monkeypatch.setattr("requests.get", _track)
    result = fetch_country_data("http://169.254.169.254/latest/meta-data/")
    assert result is None
    assert called["n"] == 0
    out = capsys.readouterr().out
    assert "allowlist" in out


def test_fetch_country_data_allowlist_extended_via_env(monkeypatch):
    """MTD_NETWORK_ALLOW_HOSTS extends the allowlist."""
    payload = {"status": "success", "country": "Custom"}
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(200, payload)
    )
    _allow_host(monkeypatch, "custom-geoip.local")

    result = fetch_country_data("http://custom-geoip.local/")
    assert result == "Custom"


# ---------------------------------------------------------------------------
# check_mirror_url
# ---------------------------------------------------------------------------

def test_check_mirror_url_200_returns_true(monkeypatch):
    """HTTP 200 → True."""
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(200)
    )
    # storage.googleapis.com is in the default allowlist
    assert check_mirror_url("http://storage.googleapis.com/cd/") is True


def test_check_mirror_url_400_returns_true(monkeypatch):
    """HTTP 400 → True.

    Selenium's driver-cache CDN returns 400 for root-level GET requests
    while still being fully functional, so 400 is treated as 'alive'.
    """
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(400)
    )
    assert check_mirror_url("http://storage.googleapis.com/cd/") is True


def test_check_mirror_url_500_returns_false(monkeypatch):
    """HTTP 500 → False."""
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(500)
    )
    assert check_mirror_url("http://storage.googleapis.com/cd/") is False


def test_check_mirror_url_request_exception_returns_false(monkeypatch):
    """RequestException → False."""
    def _raise(*a, **kw):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("requests.get", _raise)
    assert check_mirror_url("http://storage.googleapis.com/cd/") is False


def test_check_mirror_url_host_not_in_allowlist_returns_false(monkeypatch, capsys):
    """SSRF guard: hostname not in allowlist → False, never call requests.get."""
    called = {"n": 0}

    def _track(*a, **kw):
        called["n"] += 1
        return _make_response(200)

    monkeypatch.setattr("requests.get", _track)
    assert check_mirror_url("http://169.254.169.254/") is False
    assert called["n"] == 0
    out = capsys.readouterr().out
    assert "allowlist" in out


# ---------------------------------------------------------------------------
# set_se_driver_mirror_url_if_needed
# ---------------------------------------------------------------------------

def test_set_mirror_country_not_restricted_does_not_set_env(monkeypatch, capsys):
    """Country not in restricted list → SE_DRIVER_MIRROR_URL not set + message printed."""
    monkeypatch.delenv("SE_DRIVER_MIRROR_URL", raising=False)

    set_se_driver_mirror_url_if_needed(
        "Australia",
        "http://storage.googleapis.com/cd/",
        restricted_countries=["Iran", "China"],
    )

    import os
    assert "SE_DRIVER_MIRROR_URL" not in os.environ

    captured = capsys.readouterr()
    assert "Australia" in captured.out


def test_set_mirror_country_restricted_mirror_200_sets_env(monkeypatch):
    """Country in restricted list AND mirror responds 200 → env var is set."""
    monkeypatch.delenv("SE_DRIVER_MIRROR_URL", raising=False)
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(200)
    )

    set_se_driver_mirror_url_if_needed(
        "Iran",
        "http://storage.googleapis.com/cd/",
        restricted_countries=["Iran", "China"],
    )

    import os
    assert os.environ.get("SE_DRIVER_MIRROR_URL") == "http://storage.googleapis.com/cd/"


def test_set_mirror_country_restricted_mirror_url_none_does_not_set_env(monkeypatch):
    """Country in restricted list BUT mirror_url is None → short-circuit, env var not set."""
    monkeypatch.delenv("SE_DRIVER_MIRROR_URL", raising=False)

    set_se_driver_mirror_url_if_needed(
        "Iran",
        None,
        restricted_countries=["Iran", "China"],
    )

    import os
    assert "SE_DRIVER_MIRROR_URL" not in os.environ


def test_set_mirror_country_restricted_mirror_500_does_not_set_env(monkeypatch, capsys):
    """Country in restricted list BUT mirror responds 500 → env var not set + 'did not respond' printed."""
    monkeypatch.delenv("SE_DRIVER_MIRROR_URL", raising=False)
    monkeypatch.setattr(
        "requests.get", lambda *a, **kw: _make_response(500)
    )

    set_se_driver_mirror_url_if_needed(
        "China",
        "http://storage.googleapis.com/cd/",
        restricted_countries=["Iran", "China"],
    )

    import os
    assert "SE_DRIVER_MIRROR_URL" not in os.environ

    captured = capsys.readouterr()
    assert "did not respond" in captured.out
