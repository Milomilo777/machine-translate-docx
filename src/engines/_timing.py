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


# ── ChatGPT-web (chatgpt.com guest session) ────────────────────────────────
# Active path: ``selenium_chrome_chatgpt_translate`` in ``engines/chatgpt_web.py``.

CHATGPT_WEB_PRE_SLEEP: Final[float] = 0.0
"""OURS: was ``0.9`` in phase 8, now ``0.0`` to match LEGACY. The
legacy code has no pre-sleep — each call's ``delete_all_cookies()`` +
``driver.get("https://chatgpt.com/")`` is the de-facto throttle. The
0.9 s was a defensive guard added before we tested with real traffic;
on guest sessions the host's page-load time alone is enough to keep
us under any rate-limit threshold."""

CHATGPT_WEB_ACCEPT_BUTTON_WAIT: Final[float] = 0.2
"""LEGACY: ``WebDriverWait(0.2)`` for the Accept-all button after page
load."""

CHATGPT_WEB_LOGGED_OUT_LINK_WAIT: Final[float] = 2.5
"""OURS: ``WebDriverWait(2.5)`` (legacy was 1.2). chatgpt.com guest
sessions in 2026 take longer to render the modal than they did during
phase 8; 1.2 s often missed it and the modal blocked the textarea
click that follows. Called twice in sequence — the second is the
re-attempt after the first close shifts the layout."""

CHATGPT_WEB_STAY_LOGGED_OUT_WAIT: Final[float] = 0.5
"""OURS: ``WebDriverWait(0.5)`` (legacy was 0.3). Same reasoning as
``CHATGPT_WEB_LOGGED_OUT_LINK_WAIT``."""

CHATGPT_WEB_AFTER_INJECT_SLEEP: Final[float] = 2.0
"""OURS: ``sleep(2)`` after the JS textarea injection, before clicking
submit (legacy was 1.0). The composer needs a tick to register the
injected text before submit becomes clickable; 1 s sometimes raced."""

CHATGPT_WEB_STREAMING_POLL: Final[float] = 0.25
"""LEGACY: ``time.sleep(0.25)`` per iteration of the Stop-streaming
poll loop."""

CHATGPT_WEB_MAX_STREAMING_WAIT: Final[float] = 60.0
"""OURS: ``max_wait_time = 60`` (legacy was 40). Longer subtitle
blocks need more streaming time; the loop exits early as soon as the
Stop button disappears, so a higher cap doesn't slow the happy path."""


# ── Perplexity-web (perplexity.ai via google.com search) ────────────────────
# Active path: ``selenium_chrome_perplexity_translate`` in ``engines/perplexity_web.py``.

PERPLEXITY_WEB_PRE_SLEEP: Final[float] = 0.0
"""OURS: was ``0.9`` in phase 8, now ``0.0`` to match LEGACY. Same
reasoning as ``CHATGPT_WEB_PRE_SLEEP``."""

PERPLEXITY_WEB_GOOGLE_ACCEPT_WAIT: Final[float] = 0.2
"""LEGACY: ``WebDriverWait(0.2)`` for Accept-all on google.com (the
anti-bot dance starts there)."""

PERPLEXITY_WEB_LINK_SCROLL_WAIT: Final[float] = 0.2
"""LEGACY: ``time.sleep(0.2)`` after scrolling the perplexity link
into view, before the JS click."""

PERPLEXITY_WEB_GOOGLE_LINK_WAIT: Final[float] = 5.0
"""LEGACY: ``WebDriverWait(5)`` for the perplexity link on google
search results."""

PERPLEXITY_WEB_TEXTAREA_WAIT: Final[float] = 10.0
"""OURS: ``WebDriverWait(10)`` (legacy was 7). perplexity.ai got
heavier in 2026 — guest sessions can take ~5 s just to render the
ask-input box."""

PERPLEXITY_WEB_SUBMIT_BUTTON_WAIT: Final[float] = 5.0
"""OURS: ``WebDriverWait(5)`` (legacy was 1). The Submit button only
becomes enabled after the textarea registers the pasted text;
1 s often raced and missed it, causing the engine to bail before
ever submitting. User-reported: "perplexity opens the site, doesn't
give it time to translate, closes and reopens" — this is the wait
that was too short."""

PERPLEXITY_WEB_AFTER_SUBMIT_SLEEP: Final[float] = 2.0
"""OURS: ``time.sleep(2)`` after the submit click (legacy was 1).
Lets the Stop-generating button render before we start polling for
its disappearance — otherwise the first poll sees no button and the
loop exits as if generation already finished."""

PERPLEXITY_WEB_STOP_BUTTON_POLL: Final[float] = 0.5
"""OURS: ``time.sleep(0.5)`` per Stop-generating poll (legacy was
0.25). The fast cadence wasn't necessary — perplexity's streaming
runs for seconds at minimum, so 0.5 s halves the CPU spin without
delaying the exit."""

PERPLEXITY_WEB_STOP_BUTTON_TIMEOUT: Final[float] = 300.0
"""LEGACY: ``timeout = 300``. Max seconds to wait for the
Stop-generating button to disappear. Long because perplexity's
"Pro Search" mode can stream for a couple of minutes."""

PERPLEXITY_WEB_STOP_BUTTON_POLL_INTERVAL: Final[float] = 1.0
"""LEGACY: ``poll_interval = 1``. The fast-path uses
``PERPLEXITY_WEB_STOP_BUTTON_POLL``; this is the slow-path interval
when the Stop button is briefly missing from the DOM."""

PERPLEXITY_WEB_PROSE_FIRST_WAIT: Final[float] = 8.0
"""OURS: ``WebDriverWait(8)`` (legacy was 2.5). The prose div
sometimes appears late on slower guest sessions; 2.5 s missed it
and triggered the retry path immediately."""

PERPLEXITY_WEB_PROSE_RETRY_SLEEP: Final[float] = 0.5
"""OURS: ``time.sleep(0.5)`` before the prose div retry (legacy was
0.25). Gives the page a tick to actually finish painting after
streaming ends."""

PERPLEXITY_WEB_PROSE_VISIBLE_WAIT: Final[float] = 15.0
"""OURS: ``WebDriverWait(15)`` (legacy was 5). The retry waits up
to 15 s for the prose div to be visible — the whole pipeline before
this point can take 30+ s on slow sessions, so a longer tail wait
here is the cheap fix that turns "looped" into "succeeded once"."""


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
    "CHATGPT_WEB_PRE_SLEEP",
    "CHATGPT_WEB_ACCEPT_BUTTON_WAIT",
    "CHATGPT_WEB_LOGGED_OUT_LINK_WAIT",
    "CHATGPT_WEB_STAY_LOGGED_OUT_WAIT",
    "CHATGPT_WEB_AFTER_INJECT_SLEEP",
    "CHATGPT_WEB_STREAMING_POLL",
    "CHATGPT_WEB_MAX_STREAMING_WAIT",
    "PERPLEXITY_WEB_PRE_SLEEP",
    "PERPLEXITY_WEB_GOOGLE_ACCEPT_WAIT",
    "PERPLEXITY_WEB_LINK_SCROLL_WAIT",
    "PERPLEXITY_WEB_GOOGLE_LINK_WAIT",
    "PERPLEXITY_WEB_TEXTAREA_WAIT",
    "PERPLEXITY_WEB_SUBMIT_BUTTON_WAIT",
    "PERPLEXITY_WEB_AFTER_SUBMIT_SLEEP",
    "PERPLEXITY_WEB_STOP_BUTTON_POLL",
    "PERPLEXITY_WEB_STOP_BUTTON_TIMEOUT",
    "PERPLEXITY_WEB_STOP_BUTTON_POLL_INTERVAL",
    "PERPLEXITY_WEB_PROSE_FIRST_WAIT",
    "PERPLEXITY_WEB_PROSE_RETRY_SLEEP",
    "PERPLEXITY_WEB_PROSE_VISIBLE_WAIT",
]
