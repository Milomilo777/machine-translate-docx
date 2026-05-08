"""Mock-based tests for the selenium_utils package.

No real Chrome / Firefox / network — every test stubs the WebDriver.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from selenium.common.exceptions import WebDriverException

from runtime import RuntimeContext
from selenium_utils import (
    safe_click,
    browser_fill_form_field_value,
    set_chrome_window_2_3_screen,
    minimize_browser,
)


# ── safe_click ────────────────────────────────────────────────────────────────

def test_safe_click_invokes_js_click():
    drv     = MagicMock()
    element = MagicMock()
    safe_click(drv, element)
    drv.execute_script.assert_called_once_with("arguments[0].click();", element)


def test_safe_click_swallows_webdriver_exception():
    drv = MagicMock()
    drv.execute_script.side_effect = WebDriverException("boom")
    element = MagicMock()
    # Must not raise.
    safe_click(drv, element)


# ── set_chrome_window_2_3_screen ──────────────────────────────────────────────

def test_set_chrome_window_caches_position_on_first_call():
    ctx = RuntimeContext.empty()
    drv = MagicMock()
    drv.execute_script.side_effect = lambda script: 1400 if "Width" in script else 1000
    ctx.browser.driver = drv

    assert ctx.browser.cached_window_pos is None
    set_chrome_window_2_3_screen(ctx)
    # After the first call, the position is cached.
    assert ctx.browser.cached_window_pos is not None
    cached = ctx.browser.cached_window_pos

    # Second call reuses the cached position.
    set_chrome_window_2_3_screen(ctx)
    assert ctx.browser.cached_window_pos == cached


# ── minimize_browser ──────────────────────────────────────────────────────────

def test_minimize_browser_skipped_in_api_mode():
    ctx = RuntimeContext.empty()
    ctx.flags.use_api = True
    ctx.browser.driver = MagicMock()
    minimize_browser(ctx)
    ctx.browser.driver.minimize_window.assert_not_called()


def test_minimize_browser_skipped_in_split_only_mode():
    ctx = RuntimeContext.empty()
    ctx.flags.splitonly = True
    ctx.browser.driver = MagicMock()
    minimize_browser(ctx)
    ctx.browser.driver.minimize_window.assert_not_called()


def test_minimize_browser_called_for_real_engine_run():
    ctx = RuntimeContext.empty()
    ctx.flags.use_api   = False
    ctx.flags.splitonly = False
    ctx.browser.driver = MagicMock()
    minimize_browser(ctx)
    ctx.browser.driver.minimize_window.assert_called_once()


# ── browser_fill_form_field_value ─────────────────────────────────────────────

def test_browser_fill_form_swallows_exceptions(monkeypatch):
    """If the WebDriverWait times out, the helper logs and returns None."""
    ctx = RuntimeContext.empty()
    ctx.browser.driver = MagicMock()
    # Make WebDriverWait().until() raise.
    import selenium_utils.forms as forms_mod

    class _Boom(Exception):
        pass

    class _DummyWait:
        def __init__(self, *a, **kw):
            pass

        def until(self, *a, **kw):
            raise _Boom("timeout")

    monkeypatch.setattr(forms_mod, "WebDriverWait", _DummyWait)
    # Must not raise:
    browser_fill_form_field_value(ctx, "input#email", "x@example.com")
