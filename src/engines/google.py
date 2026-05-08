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

import re
import time
import traceback
from urllib.parse import urlencode, quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from runtime import RuntimeContext
from selenium_utils import safe_click

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
        traceback.format_exc()


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
        except Exception:
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
            except Exception:
                print("ERROR: Page load timeout reached.")
            button = WebDriverWait(ctx.browser.driver, 0.01).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Accept all']]")
                )
            )
            safe_click(ctx.browser.driver, button)
        except Exception:
            pass

        # `Browse your files` button — historical sentinel; not actually used.
        try:
            ctx.browser.driver.find_element(
                By.XPATH, "//button[.//span[text()='Browse your files']]"
            )
        except Exception:
            pass

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

        try:
            copy_translation_element = (
                "//button[@aria-label='Copy to clipboard' and not(@disabled) "
                "and (@aria-disabled='false' or not(@aria-disabled))]"
            )
            WebDriverWait(ctx.browser.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, copy_translation_element))
            )
        except Exception:
            print(traceback.format_exc())

        res_element_xpath = "//textarea[@lang='%s']" % (ctx.language.dest_lang)
        regex_still_translating_str = '$Translation'

        ctx.browser.driver.execute_script("window.focus();")
        selenium_chrome_google_click_cookies_consent_button(ctx)

        if re.search(regex_still_translating_str, to_translate):
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
            while re.search(regex_still_translating_str, translation):
                print("\nStill waiting for translation........\n")
                time.sleep(1)
                try:
                    result_element = WebDriverWait(ctx.browser.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, res_element_xpath))
                    )
                    translation = result_element.get_attribute('innerHTML')
                    translation = translation.unescape(translation)
                except Exception:
                    print(traceback.format_exc())

    except Exception:
        print(traceback.format_exc())

    # Force-read page_source for parity with the historical body (some
    # encoding pre-warm side effects depend on this access).
    ctx.browser.driver.page_source

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
