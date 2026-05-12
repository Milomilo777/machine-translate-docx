"""RuntimeContext — structured replacement for the entry script's globals.

The entry script ``machine-translate-docx.py`` historically carries ~80
module-level globals that are mutated across ~100 ``global`` statements in
~70 functions. ``analysis-raw.md`` § 3 catalogues the full set.

This module groups those globals into seven dataclasses, all bundled into a
single ``RuntimeContext``:

    RuntimeContext
        ├── flags     : Flags          — CLI flags (use_api, splitonly, …)
        ├── language  : LanguageCtx    — src + dest lang, names, font, RTL
        ├── engine    : EngineCtx      — current engine + dispatcher pointer
        ├── openai    : OpenAICtx      — translator, polisher, translation_log
        ├── docx      : DocxCtx        — 22+ parallel arrays + counters
        ├── browser   : BrowserCtx     — Selenium driver + Chrome options +
        │                                 per-engine session flags
        └── config    : ConfigCtx      — JSON configuration + block-size cap

The intent is that future phases thread ``ctx`` as the first argument into
every function and replace ``global x`` declarations with attribute access
on the relevant sub-context. ``DocxCtx``'s arrays preserve the existing
``+1`` indexing convention from ``read_and_parse_docx_document`` — see the
field comments below.

Two fragile behaviors documented for the future migrator:

  1. **DOCX parallel arrays.** All 22+ are sized ``numrows + 1`` and indexed
     ``[i + 1]`` throughout the read/write paths. Field types use
     ``list[str]`` / ``list[int]`` for clarity, not tuples.

  2. **DeepL phrasesblock → singlephrase fallback.** On DeepL failure, the
     entry script flips ``ctx.engine.method`` from ``"phrasesblock"`` to
     ``"singlephrase"``, calls ``set_translation_function(ctx)`` to re-point
     ``ctx.engine.dispatcher``, closes the Selenium driver, and creates a
     fresh one. ``EngineCtx.method`` and ``EngineCtx.dispatcher`` are both
     mutable for this reason.

The module is callable today: ``RuntimeContext.empty()`` returns a clean
default. Per-function threading and the deletion of ``global`` statements
in the entry script remain as a follow-up; this file is the foundation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "Flags",
    "LanguageCtx",
    "EngineCtx",
    "OpenAICtx",
    "DocxCtx",
    "BrowserCtx",
    "ConfigCtx",
    "RuntimeContext",
]


# ── CLI flags ────────────────────────────────────────────────────────────────

@dataclass
class Flags:
    """Boolean / argparse-derived flags that tweak control flow.

    Path-shaped CLI inputs (input docx, computed output path, optional
    xlsx replace file) live here too — they are CLI-derived state of
    the same lifecycle as the booleans.
    """

    use_api:           bool = False
    splitonly:         bool = False
    split_translation: bool = False
    split_engine:      str | None = None
    # Persian Double Lines aligner LLM threshold (0..100). 0 = mechanical-only
    # (default, current aligner behaviour). 100 = fully model-driven. Wired
    # end-to-end from the legacy frontend slider through to FASubtitleAligner;
    # currently a no-op because the aligner ships purely mechanical.
    aligner_llm_threshold: int = 0
    with_polish:       bool = False
    showbrowser:       bool = False
    exitonsuccess:     bool = False
    silent:            bool = False
    viewdocx:          bool = False
    verbose:           bool = False
    client_ip:         str | None = None

    # Paths (CLI input + computed output)
    word_file_to_translate:              str | None = None
    word_file_to_translate_save_as_path: str | None = None
    xlsxreplacefile:                     str | None = None

    # OpenAI model selection (CLI --aimodel; defaults applied where used)
    aimodel: str | None = None


# ── language ──────────────────────────────────────────────────────────────────

@dataclass
class LanguageCtx:
    """Source and destination language metadata."""

    src_lang:       str = "en"
    dest_lang:      str = ""
    src_lang_name:  str = ""
    dest_lang_name: str = ""
    dest_lang_tag:  str = ""    # e.g. 'fa-IR' for Office spell-check
    dest_font:      str | None = None


# ── engine dispatch ───────────────────────────────────────────────────────────

# Signature of the per-call translate function set by ``set_translation_function``.
DispatcherFn = Callable[..., Any]


@dataclass
class EngineCtx:
    """Active translation engine + its method-specific dispatcher.

    ``dispatcher`` is the function pointer historically held in the global
    ``selenium_chrome_machine_translate_once``. It is reassigned during the
    DeepL phrasesblock → singlephrase fallback (see module docstring).
    """

    engine:     str = ""               # 'google' | 'deepl' | 'chatgpt' | 'perplexity'
    method:     str = ""               # 'phrasesblock' | 'singlephrase' | 'api' | 'webservice' | 'textfile' | 'xlsxfile' | 'javascript' | 'web'
    dispatcher: DispatcherFn | None = None


# ── OpenAI integration ────────────────────────────────────────────────────────

@dataclass
class OpenAICtx:
    """OpenAI translator / polisher instances and the structured run log.

    ``translation_log`` is the dict consumed by ``write_translation_log`` and
    carries the ``"blocks"`` shape contracted by the block-loop and aligner
    code paths. Its layout is intentionally unconstrained here; the entry
    script + ``aligner_per`` own the schema.
    """

    translator: Any = None             # OpenAITranslator
    polisher:   Any = None             # OpenAIPolisher
    translation_log: dict = field(default_factory=dict)


# ── DOCX parallel arrays ──────────────────────────────────────────────────────

@dataclass
class DocxCtx:
    """The 22+ parallel arrays produced by ``read_and_parse_docx_document``.

    All arrays are sized ``numrows + 1`` and indexed ``[i + 1]`` throughout.
    Do not change the +1 convention without rewriting every reader/writer.
    """

    # ── source (EN) side ────────────────────────────────────────────────────
    from_text_table:                              list[str] = field(default_factory=list)
    from_text_is_greyed_table:                    list[int] = field(default_factory=list)
    from_text_is_red_color_table:                 list[int] = field(default_factory=list)
    from_text_is_end_of_line_table:               list[int] = field(default_factory=list)
    from_text_is_beginning_of_line_table:         list[int] = field(default_factory=list)
    from_text_is_empty_line_table:                list[int] = field(default_factory=list)
    from_text_is_conditional_end_of_line_table:   list[int] = field(default_factory=list)
    from_text_by_phrase_separator_table:          list[str] = field(default_factory=list)
    from_text_by_phrase_table:                    list[str] = field(default_factory=list)
    from_text_nb_lines_in_phrase:                 list[int] = field(default_factory=list)
    from_text_nb_lines_in_cell:                   list[int] = field(default_factory=list)
    from_text_is_read:                            list[int] = field(default_factory=list)

    # ── target (FA / etc.) side ─────────────────────────────────────────────
    to_text_by_phrase_separator_table:            list[str] = field(default_factory=list)
    to_text_by_phrase_separator_removed_table:    list[str] = field(default_factory=list)
    to_text_splited_table1:                       list[str] = field(default_factory=list)
    to_text_by_phrase_table:                      list[str] = field(default_factory=list)
    to_text_table:                                list[str] = field(default_factory=list)
    to_raw_translated_table:                      list[str] = field(default_factory=list)
    to_text_removed_line_separator:               list[str] = field(default_factory=list)
    translation_result_using_separator:           list[str] = field(default_factory=list)
    translation_result_phrase_array:              list[list] = field(default_factory=list)
    translation_result:                           list[str] = field(default_factory=list)

    # ── table geometry + counters ───────────────────────────────────────────
    table:                       Any = None       # python-docx Table
    table_cells:                 list[list[str]] = field(default_factory=list)
    numrows:                     int = 0
    numcols:                     int = 0
    word_translation_table_length: int = 0

    # ── document handle + output mode ───────────────────────────────────────
    # Threaded in G1 (2026-05-10) so read_and_parse_docx_document and
    # get_cell_data can be extracted into src/docx_io/ without re-reading
    # module globals.
    docxdoc:                     Any  = None      # python-docx Document
    use_html:                    bool = False     # CGI-style HTML output flag

    docxfile_table_number_of_phrases:    int = 0
    docxfile_table_number_of_characters: int = 0
    docxfile_table_number_of_words:      int = 0
    phrase_number_of_words:              int = 0

    # Defensive lock: deepcopy of every <w:tc> XML element in columns 0 + 1
    # captured at parse time. ``save_docx_file`` restores these before
    # writing the docx to disk, guaranteeing the source-language column
    # is never modified by any engine, helper, or future code path —
    # even if a leak slips into a translation-memory replacement loop.
    # Keyed by (row_index, col_index); value is a deepcopy'd lxml element.
    source_columns_snapshot:             Any = field(default_factory=dict)

    translation_errors_count:            int = 0
    translation_array:                   list = field(default_factory=list)
    blocks_nchar_max_to_translate_array: list = field(default_factory=list)


# ── browser / Selenium ────────────────────────────────────────────────────────

@dataclass
class BrowserCtx:
    """Selenium WebDriver state plus per-engine session flags.

    ``driver`` and ``webdriver_module`` are the two fields that change at
    runtime: ``webdriver_module`` is the import target (selenium vs
    undetected_chromedriver) chosen at module-import time based on the
    requested engine, and ``driver`` is the live ``Chrome`` instance.
    The boolean flags below are sticky once-per-session triggers used by
    engine code to decide whether a cookie banner / install-extension
    overlay needs to be closed (only on first encounter).
    """

    driver:           Any = None         # selenium.webdriver.* | undetected_chromedriver instance
    webdriver_module: Any = None         # selenium.webdriver | undetected_chromedriver (module)
    chrome_options:   Any = None         # ChromeOptions
    chromedriverpath: str | None = None
    service:          Any = None         # selenium.webdriver.chrome.service.Service
    driver_path:      str | None = None
    cached_window_pos: tuple[int, int] | None = None

    # ── DeepL session ───────────────────────────────────────────────────────
    logged_into_deepl:                bool = False
    tried_login_in_deepl:             bool = False
    deepl_nb_clear_cached_times:      int = 0
    numerrors_deepl:                  int = 0
    deepl_sleep_wait_translation_seconds: float = 0.1

    # ── Google Translate session ────────────────────────────────────────────
    found_google_cookies_consent_button: bool = False
    google_translate_first_page_loaded:  bool = False

    # ── Generic UI nuisance suppressors (cookie banners, etc.) ──────────────
    closed_cookies_accept_message_bool:      bool = False
    close_install_extension_message_bool:    bool = False


# ── runtime configuration ─────────────────────────────────────────────────────

@dataclass
class ConfigCtx:
    """Runtime configuration loaded from JSON sources (online + local +
    ``DefaultJsonConfiguration``). Populated at module-load time, then
    handed into ``RuntimeContext`` for downstream readers.

    ``max_translation_block_size`` is the only mutable field. It starts
    at the engine-derived default and may be bumped by DeepL login when
    the account exposes a higher account-tier limit (see
    ``selenium_chrome_deepl_log_in``).
    """

    json_configuration_array:    list = field(default_factory=list)
    max_translation_block_size:  int  = 1500
    # 2026-05-10 G2 — colour list looked up by `get_cell_data` to decide
    # whether a shaded paragraph / run should be ignored. Populated from
    # the merged JSON configuration in the entry script after parsing.
    shading_color_ignore_text:   list[str] = field(default_factory=list)


# ── top-level container ───────────────────────────────────────────────────────

@dataclass
class RuntimeContext:
    """Bundle of all sub-contexts. Pass ``ctx`` as the first arg to migrated
    functions in place of the historical module-level globals."""

    flags:    Flags       = field(default_factory=Flags)
    language: LanguageCtx = field(default_factory=LanguageCtx)
    engine:   EngineCtx   = field(default_factory=EngineCtx)
    openai:   OpenAICtx   = field(default_factory=OpenAICtx)
    docx:     DocxCtx     = field(default_factory=DocxCtx)
    browser:  BrowserCtx  = field(default_factory=BrowserCtx)
    config:   ConfigCtx   = field(default_factory=ConfigCtx)

    @classmethod
    def empty(cls) -> RuntimeContext:
        """Return a fresh ``RuntimeContext`` with every sub-context defaulted."""
        return cls()
