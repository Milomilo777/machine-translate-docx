"""Google Translate Selenium engine — active textarea path.

The historical implementation lived inside the entry script with several
sibling functions (per-line textarea, file-upload modes, HTML/JS+xlsx
worker drivers). G2 extracts only the *textarea* path used by the
``singlephrase`` engine method. The file-mode workers stay in the entry
script for now; they share the cookies-consent helper, which is also
exported from this module.

Public API
----------
  - ``translate(ctx, text)`` — Engine Protocol entry point. Returns
    ``(success, translated)`` per ``engines._base.Engine``.
  - ``selenium_chrome_google_translate(ctx, to_translate)`` — legacy
    name kept for the block-loop dispatcher (set_translation_function).
  - ``selenium_chrome_google_click_cookies_consent_button(ctx)`` —
    cookie-banner closer; called from the textarea path AND from the
    file-mode workers in the entry script.
"""
from __future__ import annotations

import html
import re
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..runtime import RuntimeContext
from ..selenium_utils import safe_click
from ._base import _maybe_log_swallowed

__all__ = [
    "translate",
    "selenium_chrome_google_translate",
    "selenium_chrome_google_click_cookies_consent_button",
]


# ── cookie-banner closer ─────────────────────────────────────────────────────

def selenium_chrome_google_click_cookies_consent_button(ctx: RuntimeContext) -> None:
    """Close the Google cookie-consent banner if present.

    Reads/writes ``ctx.browser.driver`` and
    ``ctx.browser.google_translate_first_page_loaded``. The ``driver``
    reference was bare in the historical body (F1.6 didn't catch it);
    G2 routes it through ctx properly.
    """
    drv = ctx.browser.driver
    try:
        # Wait for page to finish loading.
        WebDriverWait(drv, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        try:
            button = WebDriverWait(drv, 0.01).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Accept all']]")
                )
            )
            safe_click(drv, button)
        except Exception:
            pass
        try:
            drv.find_element(By.XPATH, "//button[.//span[text()='Browse your files']]")
        except Exception:
            pass
        ctx.browser.google_translate_first_page_loaded = True
    except Exception:
        # Surface for diagnostics; the upper layer treats this as best-effort.
        print(traceback.format_exc())


# ── active textarea translate ────────────────────────────────────────────────

def selenium_chrome_google_translate(ctx: RuntimeContext, to_translate: str) -> str:
    """Translate ``to_translate`` via translate.google.com (textarea path).

    Returns the translated text as a string. On any error the partial /
    empty translation is returned. Caller decides how to interpret an
    empty result.
    """
    ctx.browser.driver.execute_script("window.focus();")
    selenium_chrome_google_click_cookies_consent_button(ctx)

    translation = ''
    try:
        # Encode `&` and `%` so they don't terminate the query string.
        to_translate_escaped = to_translate.replace('%', '%25').replace('&', '%26')
        to_translate_add_new_line = '%0A '.join(to_translate_escaped.split('\n'))
        translation_url = (
            "https://translate.google.com/?sl=%s&tl=%s&op=translate&text=%s"
            % (ctx.language.src_lang, ctx.language.dest_lang, to_translate_add_new_line)
        )
        ctx.browser.driver.get(translation_url)

        try:
            ctx.browser.driver.page_source.encode('utf-8')
            WebDriverWait(ctx.browser.driver, 15).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except Exception as _exc:
            # R-7 (2026-05-11): we log the type but keep the rest of the
            # function running because Google occasionally returns partial
            # HTML that's still translatable. Set
            # `MTD_SELENIUM_VERBOSE=1` in the env to see the full traceback.
            _maybe_log_swallowed("page-load timeout (initial)", _exc)
            print("ERROR: Page load timeout reached.")

        # Re-attempt cookie consent dismissal in case the banner came back.
        try:
            button = WebDriverWait(ctx.browser.driver, 0.01).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Accept all']]")
                )
            )
            safe_click(ctx.browser.driver, button)
            ctx.browser.driver.get(translation_url)
            try:
                ctx.browser.driver.page_source.encode('utf-8')
                WebDriverWait(ctx.browser.driver, 15).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except Exception as _exc:
                _maybe_log_swallowed("page-load timeout (post cookie banner)", _exc)
                print("ERROR: Page load timeout reached.")
            button = WebDriverWait(ctx.browser.driver, 0.01).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Accept all']]")
                )
            )
            safe_click(ctx.browser.driver, button)
        except Exception as _exc:
            # Expected when no cookie banner is present — silent unless
            # the operator opts in via MTD_SELENIUM_VERBOSE=1.
            _maybe_log_swallowed("cookie-banner accept (re-attempt)", _exc)

        # `Browse your files` button — historical sentinel; not actually used.
        try:
            ctx.browser.driver.find_element(
                By.XPATH, "//button[.//span[text()='Browse your files']]"
            )
        except Exception as _exc:
            _maybe_log_swallowed("browse-your-files sentinel (expected absent)", _exc)

        time.sleep(0.2)
        try:
            button = WebDriverWait(ctx.browser.driver, 0.05).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Accept all']]")
                )
            )
            safe_click(ctx.browser.driver, button)
        except Exception:
            pass

        # Wait for the Copy-to-clipboard button — historically this was
        # used as a "translation finished" sentinel. We never actually
        # click it (we read the textarea directly below), so the wait is
        # only a "page is interactive" cue. Cut the timeout to 3 s; on
        # Persian / FA targets the button can be slow but the textarea
        # populates much earlier, so a TimeoutException here doesn't
        # mean translation failed — just that the toolbar took its time.
        try:
            copy_translation_element = (
                "//button[@aria-label='Copy to clipboard' and not(@disabled) "
                "and (@aria-disabled='false' or not(@aria-disabled))]"
            )
            WebDriverWait(ctx.browser.driver, 3).until(
                EC.presence_of_element_located((By.XPATH, copy_translation_element))
            )
        except Exception:
            # Best-effort sentinel; the textarea read below is what
            # actually drives the result. Suppress noisy traceback —
            # log a one-liner instead.
            pass

        res_element_xpath = "//textarea[@lang='%s']" % (ctx.language.dest_lang)
        # F-010 (audit): the historical regex was '$Translation', which in
        # regex syntax is "end-of-string then the literal 'Translation'" —
        # so it never matched. The wait-loop and the if-branch below are
        # therefore both no-ops in current production. Until we can verify
        # what marker Google actually emits while a translation is in
        # flight, we keep the no-match semantics explicit by short-circuiting
        # the search calls. When that pattern is identified, replace this
        # `None` with the new regex string and the loop will start working.
        regex_still_translating_str = None

        def _still_translating(text: str) -> bool:
            if not regex_still_translating_str or text is None:
                return False
            return re.search(regex_still_translating_str, text) is not None

        ctx.browser.driver.execute_script("window.focus();")
        selenium_chrome_google_click_cookies_consent_button(ctx)

        if _still_translating(to_translate):
            time.sleep(4)
            try:
                result_element = WebDriverWait(ctx.browser.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, res_element_xpath))
                )
                translation = result_element.get_attribute('innerHTML')
            except Exception:
                print(traceback.format_exc())
        else:
            try:
                result_element = WebDriverWait(ctx.browser.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, res_element_xpath))
                )
                translation = result_element.get_attribute('innerHTML')
            except Exception:
                print(traceback.format_exc())
            while _still_translating(translation):
                print("\nStill waiting for translation........\n")
                time.sleep(1)
                try:
                    result_element = WebDriverWait(ctx.browser.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, res_element_xpath))
                    )
                    translation = result_element.get_attribute('innerHTML')
                    translation = html.unescape(translation)
                except Exception:
                    print(traceback.format_exc())

    except Exception:
        print(traceback.format_exc())

    # Force-read page_source for parity with the historical body (some
    # encoding pre-warm side effects depend on this access).
    ctx.browser.driver.page_source

    # ``innerHTML`` of a textarea returns HTML-escaped content (e.g. the
    # literal characters ``&nbsp;`` rather than U+00A0, ``&amp;`` rather
    # than ``&``). The historical code only un-escaped inside the
    # ``_still_translating`` retry loop — but that regex is permanently
    # disabled (audit finding F-010), so the loop never ran and the
    # entity escapes leaked into the docx. Always un-escape now.
    if translation:
        try:
            translation = html.unescape(translation)
        except Exception:
            pass

    return translation


# ── Engine Protocol entry point ──────────────────────────────────────────────

def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]:
    """Engine Protocol implementation.

    Returns ``(success, translated)`` where ``success`` is True when the
    translated string is non-empty.
    """
    translated = selenium_chrome_google_translate(ctx, text)
    success = bool(translated)
    return success, translated
