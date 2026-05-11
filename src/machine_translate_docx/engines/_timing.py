"""Engine timing reference — single source of truth.

Every Selenium engine in this project waits in a slightly different
shape. The values here are derived from the legacy
``translation-robot/machine-translate-docx`` repository (commit
``upstream-old/main``). They are kept verbatim where the host site has
not visibly changed and adjusted with a comment + reasoning where it
has.

The point of this module is twofold:

1. **Documentation.** Future agents do not need to re-clone the legacy
   repo to find out "how long should we wait between requests?". The
   answer is in this file.

2. **Single point of change.** If a host site rotates its UI and our
   waits become wrong, the values are tweaked here and every engine
   picks them up.

Where the value is identical to legacy, the citation reads
``LEGACY``. Where it differs, the citation reads ``OURS`` and the
comment explains why.

Conventions
-----------

  * "Block-mode" — one call carries N phrases newline-joined. Used by
    ``deepl phrasesblock``, ``google phrasesblock``, ``chatgpt-web``
    (legacy body), ``perplexity-web`` (legacy body).
  * "Phrase-mode" — one call carries one phrase. Used by
    ``google singlephrase``.
  * "Inter-request delay" — sleep BETWEEN two top-level engine calls.
    Legacy has none for any engine; the natural overhead of page
    navigation is the only throttle.

Legacy snapshot
---------------

::

    Google      time.sleep(0.2)            once, after page load
                WebDriverWait(15)          for readyState complete
                WebDriverWait(0.01)        cookie button (× several)
                WebDriverWait(15)          Copy-to-clipboard button
                WebDriverWait(10)          result textarea read
                time.sleep(1)              still-translating loop
                no inter-request delay

    DeepL       deepl_sleep_wait_translation_seconds = 0.1
                                           after page load, before busy poll
                WebDriverWait(15)          for readyState complete
                WebDriverWait(0.3)         first busy element check
                sleep(0.3)                 each busy poll iteration
                timeout_busy_translating = 50  max poll iterations
                no inter-request delay

    chatgpt-web sleep(1)                   after JS injection
                time.sleep(0.25)           each "Stop streaming" poll
                WebDriverWait(0.2)         Accept-all button
                WebDriverWait(1.2)         Stay-logged-out close (× 2)
                WebDriverWait(0.3)         Stay-logged-out link
                max_wait_time = 40         seconds for Stop-streaming
                no inter-request delay
                NOTE: each call does delete_all_cookies() + driver.get()
                — full page reload acts as the de-facto throttle.

    perplexity-web
                time.sleep(0.2)            once, after google search scroll
                WebDriverWait(0.2)         Accept-all on google.com
                WebDriverWait(5)           perplexity link on google search
                WebDriverWait(7)           ask-input textarea
                WebDriverWait(1)           Submit button
                time.sleep(1)              after submit click
                time.sleep(0.25)           each Stop-generating poll
                time.sleep(1)              Stop-button hidden, before read
                WebDriverWait(2.5)         prose div first try
                time.sleep(0.25)           before second prose try
                WebDriverWait(5)           prose div visibility (second try)
                timeout = 300              max wait for stop button
                poll_interval = 1          stop-button-not-found path
                no inter-request delay
                NOTE: anti-bot dance starts at google.com → search →
                click perplexity link, then falls back to direct .get()
                if that link is missing.
"""
from __future__ import annotations

from typing import Final


# ── Google (translate.google.com) ───────────────────────────────────────────
# Active path: ``selenium_chrome_google_translate`` in ``engines/google.py``.

GOOGLE_INITIAL_WAIT: Final[float] = 0.2
"""LEGACY: ``time.sleep(0.2)`` after the URL navigation, before the cookie
poll. Lets Google's lazy-loaded controls render."""

GOOGLE_READYSTATE_TIMEOUT: Final[float] = 15.0
"""LEGACY: ``WebDriverWait(15)`` waiting for ``document.readyState ==
'complete'``. Generous to absorb cold-cache loads."""

GOOGLE_COOKIE_BUTTON_WAIT: Final[float] = 0.01
"""LEGACY: ``WebDriverWait(0.01)`` for the Accept-all button. Either it
is already there from a previous run or it isn't — no need to wait."""

GOOGLE_COPY_BUTTON_WAIT: Final[float] = 3.0
"""OURS: ``WebDriverWait(3)`` (legacy was 15 s). The textarea read below
drives the actual translation; the Copy button is only a "page is
interactive" sentinel. On Persian targets the toolbar can be slow but
the textarea populates much earlier — a 15-second timeout would tax
every call by 15 s on FA. See ``CHANGES.md`` 2026-05-10 G4."""

GOOGLE_RESULT_ELEMENT_WAIT: Final[float] = 10.0
"""LEGACY: ``WebDriverWait(10)`` for the result textarea presence."""

GOOGLE_STILL_TRANSLATING_POLL: Final[float] = 1.0
"""LEGACY: ``time.sleep(1)`` per iteration of the still-translating loop.
Currently a no-op because the legacy regex (``$Translation``) never
matches anything (audit finding F-010); kept for parity."""


# ── DeepL (deepl.com) ───────────────────────────────────────────────────────
# Active path: ``selenium_chrome_deepl_translate`` in ``engines/deepl.py``.

DEEPL_INITIAL_WAIT: Final[float] = 0.1
"""LEGACY: ``deepl_sleep_wait_translation_seconds = 0.1``. The retry
wrapper bumps this by ``× 1.1`` per retry; the seed is documented in
``machine-translate-docx.py`` line ~706."""

DEEPL_READYSTATE_TIMEOUT: Final[float] = 15.0
"""LEGACY: ``WebDriverWait(15)`` waiting for ``document.readyState``."""

DEEPL_BUSY_FIRST_CHECK_WAIT: Final[float] = 0.3
"""LEGACY: ``WebDriverWait(0.3)`` for the first busy-element presence."""

DEEPL_BUSY_POLL_SLEEP: Final[float] = 0.3
"""LEGACY: ``sleep(0.3)`` per busy-element poll iteration."""

DEEPL_BUSY_POLL_LATER_WAIT: Final[float] = 15.0
"""LEGACY: ``WebDriverWait(15)`` for the busy element after the first
hit. Allows up to 15 s for the element to reappear during streaming."""

DEEPL_BUSY_POLL_MAX_ITERATIONS: Final[int] = 50
"""LEGACY: ``timeout_busy_translating = 50``. With 0.3 s per iteration,
max wait = 15 s for translation completion."""

DEEPL_COPY_BUTTON_WAIT: Final[float] = 0.2
"""LEGACY: ``WebDriverWait(0.2)`` for the Copy-to-clipboard button.
Multiple fallback selectors share this timeout."""


# ── Removed: chatgpt-web + perplexity-web ──────────────────────────────────
# The two web-LLM engines were deleted in the 2026-05-10 cleanup pass —
# chatgpt.com Cloudflare-gates guest sessions, perplexity.ai's selectors
# kept drifting, and neither ever reached a working live state.
#
# The legacy snapshot in this module's docstring is preserved as a
# historical reference. If a future revival becomes worthwhile, the
# git tag ``archive/persian-double-lines-as-splitter-2026-05-10`` and
# the ``upstream-old`` remote both contain the working code and the
# matching constants (``CHATGPT_WEB_*``, ``PERPLEXITY_WEB_*``).


__all__ = [
    "GOOGLE_INITIAL_WAIT",
    "GOOGLE_READYSTATE_TIMEOUT",
    "GOOGLE_COOKIE_BUTTON_WAIT",
    "GOOGLE_COPY_BUTTON_WAIT",
    "GOOGLE_RESULT_ELEMENT_WAIT",
    "GOOGLE_STILL_TRANSLATING_POLL",
    "DEEPL_INITIAL_WAIT",
    "DEEPL_READYSTATE_TIMEOUT",
    "DEEPL_BUSY_FIRST_CHECK_WAIT",
    "DEEPL_BUSY_POLL_SLEEP",
    "DEEPL_BUSY_POLL_LATER_WAIT",
    "DEEPL_BUSY_POLL_MAX_ITERATIONS",
    "DEEPL_COPY_BUTTON_WAIT",
]
