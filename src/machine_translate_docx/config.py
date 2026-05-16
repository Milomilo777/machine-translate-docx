"""Static configuration: constants, language tables, regex arrays, JSON helpers.

This module contains every value that does not depend on runtime state:
language lookup dictionaries, end-of-line / beginning-of-line regex arrays,
the project's default JSON configuration string, and two pure helpers that
parse that JSON.

Runtime-derived values (e.g. ``chrome_driver_restricted_countries``,
``MAX_TRANSLATION_BLOCK_SIZE``, ``shading_color_ignore_text``) are computed
in the entry script from this module's ``DefaultJsonConfiguration`` plus
the optional online + local override files.
"""
from __future__ import annotations

import sys
import traceback
from typing import Any, Final

import json5


__all__ = [
    "DefaultJsonConfiguration",
    "validate_json_string",
    "get_nested_value_from_json_array",
    "google_translate_lang_codes",
    "deepl_translate_lang_codes",
    "office_language_tags",
    "right_to_left_languages_list",
    "eol_array",
    "eol_conditional_array",
    "bol_array",
    "MAX_LINE_SIZE",
    "COUNTRY_QUERY_HTTP_TIMEOUT",
    "DEFAULT_AI_MODEL",
    "ALIGNER_MODEL",
    "VALID_AI_MODELS",
    "is_valid_ai_model",
]


# ── OpenAI model whitelist ────────────────────────────────────────────────────
#
# Single source of truth for valid OpenAI model identifiers. Added in the
# 2026-05-10 hardening pass after a real-engine test surfaced the fact
# that `--aimodel gpt-5.5-mini` (a typo / stale dropdown value) was
# accepted by the CLI and only failed deep inside the API call with a
# 400 BadRequestError.
#
# Constraints (C1 in PROJECT_MEMORY.md):
#   - Aligner is ALWAYS ``ALIGNER_MODEL`` and that contract must not be
#     parameterised away. The constant exists so downstream code reads
#     it from one place; it is not negotiable per-call.
#   - Translator + polisher default to ``DEFAULT_AI_MODEL``. The user
#     can override with ``--aimodel`` from the CLI (validated against
#     ``VALID_AI_MODELS``) or via the v2 frontend dropdown (which must
#     also pull from this list to stay in sync).

DEFAULT_AI_MODEL: Final[str]      = "gpt-5.5"
ALIGNER_MODEL:    Final[str]      = "gpt-5.4-mini"
VALID_AI_MODELS:  Final[tuple[str, ...]] = ("gpt-5.5", "gpt-5.4-mini")


def is_valid_ai_model(model: str | None) -> bool:
    """Return True iff ``model`` is in :data:`VALID_AI_MODELS`.

    ``None`` is considered valid (it means "use the default") so the
    helper can be called from CLI parse code that hasn't applied the
    default yet.
    """
    if model is None:
        return True
    return model in VALID_AI_MODELS


# ── JSON helpers ──────────────────────────────────────────────────────────────

def validate_json_string(json_string: str | bytes) -> bool:
    """Return True if ``json_string`` parses as JSON5."""
    try:
        if isinstance(json_string, str):
            pass
        elif isinstance(json_string, bytes):
            pass
        else:
            return False
        json_obj = json5.loads(json_string)
        if json_obj is None:
            return False
        return True
    except Exception:
        # 2026-05-16 (P2.7 from master audit): route traceback to stderr.
        # ``local_launcher.py``'s stdout parser watches stdout for
        # ``Saved file name:`` and ``PROGRESS:N`` markers; bare
        # traceback text leaking into stdout could be mistaken for an
        # incomplete line (some lines start with ``"  File ..."`` which
        # technically matches "no marker yet" — harmless today, but a
        # future regex tweak could trip on it).
        print(traceback.format_exc(), file=sys.stderr)
        return False


def get_nested_value_from_json_array(
    json_array: list,
    keys: list[str],
    default_when_none: Any = None,
) -> Any:
    """Walk ``keys`` into the first JSON5 string in ``json_array`` that has them.

    Returns ``default_when_none`` if no source contains the full key path.
    """
    try:
        for json_str in json_array:
            try:
                json_obj = json5.loads(json_str)
                for key in keys:
                    if key in json_obj:
                        json_obj = json_obj[key]
                    else:
                        json_obj = None
                if json_obj is not None:
                    return json_obj
            except Exception:
                pass
        return default_when_none
    except Exception:
        print("Invalid JSON input")
        return default_when_none


# ── Default JSON configuration (used when the online + local overrides miss) ──

# The trailing keys with `_` (email_, password_) are intentionally suffixed to
# block accidental real-credential commits via the default config.
DefaultJsonConfiguration: Final[str] = """{
    "local_configuration":{
        "json_filename_path": "configuration.json"
    },
	"deepl": {
		"account": {
			"email_": "********@gmail.com",
			"password_": "********",
			"type": "free",
			"maximum_character_block": 1500
		},
		"no_account": {
			"maximum_character_block": 1500
		},
        "maximum_clear_cache_retry" : 20
	},
	"google": {
        "lang_codes" : {
        'af': 'Afrikaans',
        'sq': 'Albanian',
        'am': 'Amharic',
        'ar': 'Arabic',
        'hy': 'Armenian',
        'az': 'Azerbaijani',
        'eu': 'Basque',
        'be': 'Belarusian',
        'bn': 'Bengali',
        'bs': 'Bosnian',
        'bg': 'Bulgarian',
        'ca': 'Catalan',
        'ceb': 'Cebuano',
        'zh': 'Chinese (simplified)',
        'zh-CN': 'Chinese (simplified)',
        'zh-TW': 'Chinese (traditional)',
        'co': 'Corsican',
        'hr': 'Croatian',
        'cs': 'Czech',
        'da': 'Danish',
        'nl': 'Dutch',
        'en': 'English',
        'eo': 'Esperanto',
        'et': 'Estonian',
        'fi': 'Finnish',
        'fr': 'French',
        'fy': 'Frisian',
        'gl': 'Galician',
        'ka': 'Georgian',
        'de': 'German',
        'el': 'Greek',
        'gu': 'Gujarati',
        'ht': 'Haitian Creole',
        'ha': 'Hausa',
        'haw': 'Hawaiian',
        'iw': 'Hebrew',
        'hi': 'Hindi',
        'hmn': 'Hmong',
        'hu': 'Hungarian',
        'is': 'Icelandic',
        'ig': 'Igbo',
        'id': 'Indonesian',
        'ga': 'Irish',
        'it': 'Italian',
        'ja': 'Japanese',
        'jv': 'Javanese',
        'kn': 'Kannada',
        'kk': 'Kazakh',
        'km': 'Khmer',
        'ko': 'Korean',
        'ku': 'Kurdish',
        'ky': 'Kyrgyz',
        'lo': 'Lao',
        'la': 'Latin',
        'lv': 'Latvian',
        'lt': 'Lithuanian',
        'lb': 'Luxembourgish',
        'mk': 'Macedonian',
        'mg': 'Malagasy',
        'ms': 'Malay',
        'ml': 'Malayalam',
        'mt': 'Maltese',
        'mi': 'Maori',
        'mr': 'Marathi',
        'mn': 'Mongolian',
        'my': 'Myanmar (Burmese)',
        'ne': 'Nepali',
        'no': 'Norwegian',
        'ny': 'Nyanja (Chichewa)',
        'ps': 'Pashto',
        'fa': 'Persian',
        'pl': 'Polish',
        'pt': 'Portuguese (Portugal, Brazil)',
        'pa': 'Punjabi',
        'ro': 'Romanian',
        'ru': 'Russian',
        'sm': 'Samoan',
        'gd': 'Scots Gaelic',
        'sr': 'Serbian',
        'st': 'Sesotho',
        'sn': 'Shona',
        'sd': 'Sindhi',
        'si': 'Sinhala (Sinhalese)',
        'sk': 'Slovak',
        'sl': 'Slovenian',
        'so': 'Somali',
        'es': 'Spanish',
        'su': 'Sundanese',
        'sw': 'Swahili',
        'sv': 'Swedish',
        'tl': 'Tagalog (Filipino)',
        'tg': 'Tajik',
        'ta': 'Tamil',
        'te': 'Telugu',
        'th': 'Thai',
        'tr': 'Turkish',
        'uk': 'Ukrainian',
        'ur': 'Urdu',
        'uz': 'Uzbek',
        'vi': 'Vietnamese',
        'cy': 'Welsh',
        'xh': 'Xhosa',
        'yi': 'Yiddish',
        'yo': 'Yoruba',
        'zu': 'Zulu'
        },
		"javascript_translation": {},
		"html_translation_form": {
			"maximum_character_block": 5000
		}
	},
	"chatgpt": {
		"no_account": {
			"maximum_character_block": 1000
		},
		"api": {
			"maximum_character_block": 220000
		},
        "usage_violation_message" : "Your request was flagged as potentially violating our usage policy. Please try again with a different prompt."
	},
	"statistics": {
		"html_statistics_form_url": "https://contactdirectavecdieu.net/robot-stats.php",
		"google_sheets_statistics": {
			"no_account": {
				"google_account": "to be determined"
			}
		}
	},
	"version_checker": {
	  "javascript_json_version_checker_url": "https://translation-robot.github.io/machine-translate-docx/src/robot_js_query.html",
      "sleep_seconds_on_update": 30
	},
	"location": {
	  "primary_country_checker_url": "http://ip-api.com/json/",
	  "secondary_country_checker_url": "https://www.contactdirectavecdieu.net/geoip/index.php",
      "http_query_timeout" : 3
	},
	"chrome_driver": {
      "restricted_countries": ["North Korea", "Iran", "Syria", "Sudan", "Cuba", "Crimea"],
      "mirror_url": "https://www.contactdirectavecdieu.net/known-good-versions-with-downloads.php"
    },
    "document": {
      "microsoft_colors_link_reference" : "https://learn.microsoft.com/en-us/office/vba/api/word.wdcolor",
      "shading_color_ignore_text" : ['FFD320', 'D9D9D9', 'BFBFBF', 'A6A6A6', '808080', 'FF00FF', 'FF0000', 'F3F3F3', 'E6E6E6', 'E0E0E0', 'CCCCCC', 'C0C0C0', 'B3B3B3', 'A0A0A0', '999999', '8C8C8C',  '737373', '666666', '606060', '595959', '4C4C4C', '404040', '333333', '262626', '202020', '191919', '0C0C0C', '002060', '000080', 'FFCCFF', 'CC99FF']
    }
}"""


# ── Language lookup tables ────────────────────────────────────────────────────

# Names retained in lowercase to avoid a rename sweep across the entry script.
# These are typed as Final to signal that they are read-only mappings.

google_translate_lang_codes: Final[dict[str, str]] = {
    'af': 'Afrikaans',
    'sq': 'Albanian',
    'am': 'Amharic',
    'ar': 'Arabic',
    'hy': 'Armenian',
    'az': 'Azerbaijani',
    'eu': 'Basque',
    'be': 'Belarusian',
    'bn': 'Bengali',
    'bs': 'Bosnian',
    'bg': 'Bulgarian',
    'ca': 'Catalan',
    'ceb': 'Cebuano',
    'zh': 'Chinese (simplified)',
    'zh-CN': 'Chinese (simplified)',
    'zh-TW': 'Chinese (traditional)',
    'co': 'Corsican',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'nl': 'Dutch',
    'en': 'English',
    'eo': 'Esperanto',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'fy': 'Frisian',
    'gl': 'Galician',
    'ka': 'Georgian',
    'de': 'German',
    'el': 'Greek',
    'gu': 'Gujarati',
    'ht': 'Haitian Creole',
    'ha': 'Hausa',
    'haw': 'Hawaiian',
    'iw': 'Hebrew',
    'hi': 'Hindi',
    'hmn': 'Hmong',
    'hu': 'Hungarian',
    'is': 'Icelandic',
    'ig': 'Igbo',
    'id': 'Indonesian',
    'ga': 'Irish',
    'it': 'Italian',
    'ja': 'Japanese',
    'jv': 'Javanese',
    'kn': 'Kannada',
    'kk': 'Kazakh',
    'km': 'Khmer',
    'ko': 'Korean',
    'ku': 'Kurdish',
    'ky': 'Kyrgyz',
    'lo': 'Lao',
    'la': 'Latin',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'lb': 'Luxembourgish',
    'mk': 'Macedonian',
    'mg': 'Malagasy',
    'ms': 'Malay',
    'ml': 'Malayalam',
    'mt': 'Maltese',
    'mi': 'Maori',
    'mr': 'Marathi',
    'mn': 'Mongolian',
    'my': 'Myanmar (Burmese)',
    'ne': 'Nepali',
    'no': 'Norwegian',
    'ny': 'Nyanja (Chichewa)',
    'ps': 'Pashto',
    'fa': 'Persian',
    'pl': 'Polish',
    'pt': 'Portuguese (Portugal, Brazil)',
    'pa': 'Punjabi',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sm': 'Samoan',
    'gd': 'Scots Gaelic',
    'sr': 'Serbian',
    'st': 'Sesotho',
    'sn': 'Shona',
    'sd': 'Sindhi',
    'si': 'Sinhala (Sinhalese)',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'so': 'Somali',
    'es': 'Spanish',
    'su': 'Sundanese',
    'sw': 'Swahili',
    'sv': 'Swedish',
    'tl': 'Tagalog (Filipino)',
    'tg': 'Tajik',
    'ta': 'Tamil',
    'te': 'Telugu',
    'th': 'Thai',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'uz': 'Uzbek',
    'vi': 'Vietnamese',
    'cy': 'Welsh',
    'xh': 'Xhosa',
    'yi': 'Yiddish',
    'yo': 'Yoruba',
    'zu': 'Zulu',
}

deepl_translate_lang_codes: Final[dict[str, str]] = {
    'ace': 'Acehnese',
    'af': 'Afrikaans',
    'sq': 'Albanian',
    'ar': 'Arabic',
    'an': 'Aragonese',
    'hy': 'Armenian',
    'as': 'Assamese',
    'ay': 'Aymara',
    'az': 'Azerbaijani',
    'ba': 'Bashkir',
    'eu': 'Basque',
    'be': 'Belarusian',
    'bn': 'Bengali',
    'bho': 'Bhojpuri',
    'bs': 'Bosnian',
    'br': 'Breton',
    'bg': 'Bulgarian',
    'my': 'Burmese',
    'yue': 'Cantonese',
    'ca': 'Catalan',
    'ceb': 'Cebuano',
    'zh-hans': 'Chinese (simplified)',
    'zh-hant': 'Chinese (traditional)',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'prs': 'Dari',
    'nl': 'Dutch',
    'en-us': 'English (American)',
    'en-gb': 'English (British)',
    'eo': 'Esperanto',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'gl': 'Galician',
    'ka': 'Georgian',
    'de': 'German',
    'el': 'Greek',
    'gn': 'Guarani',
    'gu': 'Gujarati',
    'ht': 'Haitian Creole',
    'ha': 'Hausa',
    'he': 'Hebrew',
    'hi': 'Hindi',
    'hu': 'Hungarian',
    'is': 'Icelandic',
    'ig': 'Igbo',
    'id': 'Indonesian',
    'ga': 'Irish',
    'it': 'Italian',
    'ja': 'Japanese',
    'jv': 'Javanese',
    'pam': 'Kapampangan',
    'kk': 'Kazakh',
    'gom': 'Konkani',
    'ko': 'Korean',
    'kmr': 'Kurdish (Kurmanji)',
    'ckb': 'Kurdish (Sorani)',
    'ky': 'Kyrgyz',
    'la': 'Latin',
    'lv': 'Latvian',
    'ln': 'Lingala',
    'lt': 'Lithuanian',
    'lmo': 'Lombard',
    'lb': 'Luxembourgish',
    'mk': 'Macedonian',
    'mai': 'Maithili',
    'mg': 'Malagasy',
    'ms': 'Malay',
    'ml': 'Malayalam',
    'mt': 'Maltese',
    'mi': 'Maori',
    'mr': 'Marathi',
    'mn': 'Mongolian',
    'ne': 'Nepali',
    'nb': 'Norwegian (bokmål)',
    'oc': 'Occitan',
    'om': 'Oromo',
    'pag': 'Pangasinan',
    'ps': 'Pashto',
    'fa': 'Persian',
    'pl': 'Polish',
    'pt-pt': 'Portuguese',
    'pt-br': 'Portuguese (Brazilian)',
    'pa': 'Punjabi',
    'qu': 'Quechua',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sa': 'Sanskrit',
    'sr': 'Serbian',
    'st': 'Sesotho',
    'scn': 'Sicilian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'es': 'Spanish',
    'es-419': 'Spanish (Latin American)',
    'su': 'Sundanese',
    'sw': 'Swahili',
    'sv': 'Swedish',
    'tl': 'Tagalog',
    'tg': 'Tajik',
    'ta': 'Tamil',
    'tt': 'Tatar',
    'te': 'Telugu',
    'ts': 'Tsonga',
    'tn': 'Tswana',
    'tr': 'Turkish',
    'tk': 'Turkmen',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'uz': 'Uzbek',
    'vi': 'Vietnamese',
    'cy': 'Welsh',
    'wo': 'Wolof',
    'xh': 'Xhosa',
    'yi': 'Yiddish',
    'zu': 'Zulu',
}

# Office spell-check tags. Two duplicate keys (zh, pt) are preserved for
# behavioural parity — Python keeps the second value, mirroring the original.
office_language_tags: Final[dict[str, str]] = {
    'ar': 'ar-SA',
    'bg': 'bg-BG',
    'zh': 'zh-CN',
    'zh': 'zh-TW',
    'hr': 'hr-HR',
    'cs': 'cs-CZ',
    'da': 'da-DK',
    'nl': 'nl-NL',
    'en': 'en-US',
    'et': 'et-EE',
    'fi': 'fi-FI',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'el': 'el-GR',
    'he': 'he-IL',
    'hi': 'hi-IN',
    'hu': 'hu-HU',
    'id': 'id-ID',
    'it': 'it-IT',
    'ja': 'ja-JP',
    'kk': 'kk-KZ',
    'ko': 'ko-KR',
    'lv': 'lv-LV',
    'lt': 'lt-LT',
    'ms': 'ms-MY',
    'nb': 'nb-NO',
    'pl': 'pl-PL',
    'pt': 'pt-BR',
    'pt': 'pt-PT',
    'ro': 'ro-RO',
    'ru': 'ru-RU',
    'sr': 'sr-latn-RS',
    'sk': 'sk-SK',
    'sl': 'sl-SI',
    'es': 'es-ES',
    'sv': 'sv-SE',
    'th': 'th-TH',
    'tr': 'tr-TR',
    'uk': 'uk-UA',
    'vi': 'vi-VN',
}

right_to_left_languages_list: Final[dict[str, str]] = {
    'am': 'Amharic',
    'ar': 'Arabic',
    'az': 'Azerbaijani',
    'iw': 'Hebrew',
    'ku': 'Kurdish',
    'fa': 'Persian',
    'ur': 'Urdu',
}


# ── End-of-line / beginning-of-line regex arrays ──────────────────────────────

# Punctuation comments retained for archaeological reference. Many entries
# duplicate by code-point: kept verbatim from the original file to preserve
# regex iteration order observed by `is_end_of_line`.
# `…` = horizontal ellipsis, `”` = right double quotation mark.
eol_array: Final[list[str]] = [
    r'\. {0,}$', r'\! {0,}$', r'\? {0,}$', r'[\.\!\?\'] ?["”\'\)] {0,}$',
    '… {0,}$',
    '। {0,}$',  # Hindi period
    '。 {0,}$', '？ {0,}$', '！ {0,}$',  # Chinese and Japanese period
    '։ {0,}$',  # ARMENIAN FULL STOP	U+0589
    '։ {0,}$',  # full stop, georgian
    '։ {0,}$',  # FULL STOP, ARMENIAN
    '։ {0,}$',  # georgian full stop
    '۔ {0,}$',  # ARABIC FULL STOP	U+06D4
    '۔ {0,}$',  # FULL STOP, ARABIC
    '܁ {0,}$',  # SYRIAC SUPRALINEAR FULL STOP	U+0701
    '܂ {0,}$',  # SYRIAC SUBLINEAR FULL STOP	U+0702
    '። {0,}$',  # ETHIOPIC FULL STOP	U+1362
    '። {0,}$',  # FULL STOP, ETHIOPIC
    '᙮ {0,}$',  # CANADIAN SYLLABICS FULL STOP	U+166E
    '᙮ {0,}$',  # FULL STOP, CANADIAN SYLLABICS
    '᙮ {0,}$',  # SYLLABICS FULL STOP, CANADIAN
    '᠃ {0,}$',  # MONGOLIAN FULL STOP	U+1803
    '᠃ {0,}$',  # FULL STOP, MONGOLIAN
    '᠉ {0,}$',  # MONGOLIAN MANCHU FULL STOP	U+1809
    '᠉ {0,}$',  # FULL STOP, MONGOLIAN MANCHU
    '᠉ {0,}$',  # MANCHU FULL STOP, MONGOLIAN
    '⒈ {0,}$',  # DIGIT ONE FULL STOP	U+2488
    '⒉ {0,}$',  # DIGIT TWO FULL STOP
    '⒊ {0,}$',  # DIGIT THREE FULL STOP
    '⒋ {0,}$',  # DIGIT FOUR FULL STOP
    '⒌ {0,}$',  # DIGIT FIVE FULL STOP
    '⒍ {0,}$',  # DIGIT SIX FULL STOP
    '⒎ {0,}$',  # DIGIT SEVEN FULL STOP
    '⒏ {0,}$',  # DIGIT EIGHT FULL STOP
    '⒐ {0,}$',  # DIGIT NINE FULL STOP
    '⒑ {0,}$',  # NUMBER TEN FULL STOP
    '⒒ {0,}$',  # NUMBER ELEVEN FULL STOP
    '⒓ {0,}$',  # NUMBER TWELVE FULL STOP
    '⒔ {0,}$',  # NUMBER THIRTEEN FULL STOP
    '⒕ {0,}$',  # NUMBER FOURTEEN FULL STOP
    '⒖ {0,}$',  # NUMBER FIFTEEN FULL STOP
    '⒗ {0,}$',  # NUMBER SIXTEEN FULL STOP
    '⒘ {0,}$',  # NUMBER SEVENTEEN FULL STOP
    '⒙ {0,}$',  # NUMBER EIGHTEEN FULL STOP
    '⒚ {0,}$',  # NUMBER NINETEEN FULL STOP
    '⒛ {0,}$',  # NUMBER TWENTY FULL STOP
    '⳹ {0,}$',  # COPTIC OLD NUBIAN FULL STOP
    '⳾ {0,}$',  # COPTIC FULL STOP
    '⸼ {0,}$',  # STENOGRAPHIC FULL STOP
    '。 {0,}$',  # IDEOGRAPHIC FULL STOP	U+3002
    '。 {0,}$',  # FULL STOP, IDEOGRAPHIC
    '꓿ {0,}$',  # LISU PUNCTUATION FULL STOP
    '꘎ {0,}$',  # VAI FULL STOP
    '꛳ {0,}$',  # BAMUM FULL STOP
    '︒ {0,}$',  # PRESENTATION FORM FOR VERTICAL IDEOGRAPHIC FULL STOP
    '﹒ {0,}$',  # SMALL FULL STOP
    '． {0,}$',  # FULLWIDTH FULL STOP
    '｡ {0,}$',  # HALFWIDTH IDEOGRAPHIC FULL STOP
    '! {0,}$',  # EXCLAMATION MARK	U+0021
    '¡ {0,}$',  # INVERTED EXCLAMATION MARK
    '¡ {0,}$',  # EXCLAMATION MARK, INVERTED
    'ǃ {0,}$',  # latin letter exclamation mark
    'ǃ {0,}$',  # exclamation mark, latin letter
    'ǃ {0,}$',  # LATIN LETTER EXCLAMATION MARK
    '՜ {0,}$',  # ARMENIAN EXCLAMATION MARK
    '՜ {0,}$',  # EXCLAMATION MARK, ARMENIAN
    '߹ {0,}$',  # NKO EXCLAMATION MARK
    '᥄ {0,}$',  # LIMBU EXCLAMATION MARK
    '᥄ {0,}$',  # EXCLAMATION MARK, LIMBU
    '‼ {0,}$',  # DOUBLE EXCLAMATION MARK
    '‼ {0,}$',  # EXCLAMATION MARK, DOUBLE
    '⁈ {0,}$',  # QUESTION EXCLAMATION MARK
    '⁈ {0,}$',  # EXCLAMATION MARK, QUESTION
    '❕ {0,}$',  # WHITE EXCLAMATION MARK ORNAMENT
    '❕ {0,}$',  # EXCLAMATION MARK ORNAMENT, WHITE
    '❗ {0,}$',  # HEAVY EXCLAMATION MARK SYMBOL
    '❢ {0,}$',  # HEAVY EXCLAMATION MARK ORNAMENT
    '❢ {0,}$',  # EXCLAMATION MARK ORNAMENT, HEAVY
    '❣ {0,}$',  # HEAVY HEART EXCLAMATION MARK ORNAMENT
    '⹓ {0,}$',  # MEDIEVAL EXCLAMATION MARK
    'ꜝ {0,}$',  # MODIFIER LETTER RAISED EXCLAMATION MARK
    'ꜞ {0,}$',  # MODIFIER LETTER RAISED INVERTED EXCLAMATION MARK
    'ꜟ {0,}$',  # MODIFIER LETTER LOW INVERTED EXCLAMATION MARK
    '︕ {0,}$',  # PRESENTATION FORM FOR VERTICAL EXCLAMATION MARK
    '﹗ {0,}$',  # SMALL EXCLAMATION MARK
    '！ {0,}$',  # FULLWIDTH EXCLAMATION MARK
    '！ {0,}$',  # FULLWIDTH EXCLAMATION MARK
    '; {0,}$',  # question mark, greek
    r'\; {0,}$',  # greek question mark
    r'\? {0,}$',  # QUESTION MARK	U+003F
    '¿ {0,}$',  # INVERTED QUESTION MARK
    '¿ {0,}$',  # question mark, turned
    '¿ {0,}$',  # QUESTION MARK, INVERTED
    '¿ {0,}$',  # turned question mark
    '; {0,}$',  # GREEK QUESTION MARK
    '; {0,}$',  # QUESTION MARK, GREEK
    '՞ {0,}$',  # ARMENIAN QUESTION MARK
    '՞ {0,}$',  # QUESTION MARK, ARMENIAN
    '؟ {0,}$',  # ARABIC QUESTION MARK
    '؟ {0,}$',  # QUESTION MARK, ARABIC
    '፧ {0,}$',  # ETHIOPIC QUESTION MARK
    '፧ {0,}$',  # QUESTION MARK, ETHIOPIC
    '᥅ {0,}$',  # LIMBU QUESTION MARK
    '᥅ {0,}$',  # QUESTION MARK, LIMBU
    '⁇ {0,}$',  # DOUBLE QUESTION MARK
    '⁇ {0,}$',  # QUESTION MARK, DOUBLE
    '⁉ {0,}$',  # EXCLAMATION QUESTION MARK
    '⁉ {0,}$',  # QUESTION MARK, EXCLAMATION
    '❓ {0,}$',  # BLACK QUESTION MARK ORNAMENT
    '❓ {0,}$',  # QUESTION MARK ORNAMENT, BLACK
    '❔ {0,}$',  # WHITE QUESTION MARK ORNAMENT
    '❔ {0,}$',  # QUESTION MARK ORNAMENT, WHITE
    '⩻ {0,}$',  # LESS-THAN WITH QUESTION MARK ABOVE
    '⩼ {0,}$',  # GREATER-THAN WITH QUESTION MARK ABOVE
    '⳺ {0,}$',  # COPTIC OLD NUBIAN DIRECT QUESTION MARK
    '⳻ {0,}$',  # COPTIC OLD NUBIAN INDIRECT QUESTION MARK
    '⸮ {0,}$',  # REVERSED QUESTION MARK
    '⹔ {0,}$',  # MEDIEVAL QUESTION MARK
    '꘏ {0,}$',  # VAI QUESTION MARK
    '꛷ {0,}$',  # BAMUM QUESTION MARK
    '︖ {0,}$',  # PRESENTATION FORM FOR VERTICAL QUESTION MARK
    '﹖ {0,}$',  # SMALL QUESTION MARK
    '？ {0,}$',  # FULLWIDTH QUESTION MARK
]

eol_conditional_array: Final[list[str]] = [r'\" {0,}$', '” {0,}$', r'\)']
bol_array:             Final[list[str]] = [r'^[A-Z]']


# ── Misc constants ────────────────────────────────────────────────────────────

MAX_LINE_SIZE:              Final[int] = 36
COUNTRY_QUERY_HTTP_TIMEOUT: Final[int] = 3
