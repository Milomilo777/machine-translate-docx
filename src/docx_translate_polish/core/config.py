"""Configuration and constants."""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Extracted Constants from machine-translate-docx.py ---

google_translate_lang_codes = {
    'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic', 'hy': 'Armenian',
    'az': 'Azerbaijani', 'eu': 'Basque', 'be': 'Belarusian', 'bn': 'Bengali', 'bs': 'Bosnian',
    'bg': 'Bulgarian', 'ca': 'Catalan', 'ceb': 'Cebuano', 'ny': 'Chichewa', 'zh-cn': 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)', 'co': 'Corsican', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish',
    'nl': 'Dutch', 'en': 'English', 'eo': 'Esperanto', 'et': 'Estonian', 'tl': 'Filipino', 'fi': 'Finnish',
    'fr': 'French', 'fy': 'Frisian', 'gl': 'Galician', 'ka': 'Georgian', 'de': 'German', 'el': 'Greek',
    'gu': 'Gujarati', 'ht': 'Haitian Creole', 'ha': 'Hausa', 'haw': 'Hawaiian', 'iw': 'Hebrew', 'hi': 'Hindi',
    'hmn': 'Hmong', 'hu': 'Hungarian', 'is': 'Icelandic', 'ig': 'Igbo', 'id': 'Indonesian', 'ga': 'Irish',
    'it': 'Italian', 'ja': 'Japanese', 'jw': 'Javanese', 'kn': 'Kannada', 'kk': 'Kazakh', 'km': 'Khmer',
    'ko': 'Korean', 'ku': 'Kurdish (Kurmanji)', 'ky': 'Kyrgyz', 'lo': 'Lao', 'la': 'Latin', 'lv': 'Latvian',
    'lt': 'Lithuanian', 'lb': 'Luxembourgish', 'mk': 'Macedonian', 'mg': 'Malagasy', 'ms': 'Malay',
    'ml': 'Malayalam', 'mt': 'Maltese', 'mi': 'Maori', 'mr': 'Marathi', 'mn': 'Mongolian', 'my': 'Myanmar (Burmese)',
    'ne': 'Nepali', 'no': 'Norwegian', 'ps': 'Pashto', 'fa': 'Persian', 'pl': 'Polish', 'pt': 'Portuguese',
    'pa': 'Punjabi', 'ro': 'Romanian', 'ru': 'Russian', 'sm': 'Samoan', 'gd': 'Scots Gaelic', 'sr': 'Serbian',
    'st': 'Sesotho', 'sn': 'Shona', 'sd': 'Sindhi', 'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian',
    'so': 'Somali', 'es': 'Spanish', 'su': 'Sundanese', 'sw': 'Swahili', 'sv': 'Swedish', 'tg': 'Tajik',
    'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'uz': 'Uzbek',
    'vi': 'Vietnamese', 'cy': 'Welsh', 'xh': 'Xhosa', 'yi': 'Yiddish', 'yo': 'Yoruba', 'zu': 'Zulu'
}

right_to_left_languages_list = {
    'am': 'Amharic', 'ar': 'Arabic', 'az': 'Azerbaijani', 'iw': 'Hebrew', 'ku': 'Kurdish', 'fa': 'Persian', 'ur': 'Urdu'
}

shading_color_ignore_text = [
    'FFD320', 'D9D9D9', 'BFBFBF', 'A6A6A6', '808080', 'FF00FF', 'FF0000', 'F3F3F3', 'E6E6E6', 'E0E0E0', 'CCCCCC',
    'C0C0C0', 'B3B3B3', 'A0A0A0', '999999', '8C8C8C', '737373', '666666', '606060', '595959', '4C4C4C', '404040',
    '333333', '262626', '202020', '191919', '0C0C0C', '002060', '000080', 'FFCCFF', 'CC99FF'
]

office_language_tags = {
    'ar': 'ar-SA', 'bg': 'bg-BG', 'zh': 'zh-CN', 'hr': 'hr-HR', 'cs': 'cs-CZ', 'da': 'da-DK', 'nl': 'nl-NL',
    'en': 'en-US', 'et': 'et-EE', 'fi': 'fi-FI', 'fr': 'fr-FR', 'de': 'de-DE', 'el': 'el-GR', 'he': 'he-IL',
    'hi': 'hi-IN', 'hu': 'hu-HU', 'id': 'id-ID', 'it': 'it-IT', 'ja': 'ja-JP', 'kk': 'kk-KZ', 'ko': 'ko-KR',
    'lv': 'lv-LV', 'lt': 'lt-LT', 'ms': 'ms-MY', 'nb': 'nb-NO', 'pl': 'pl-PL', 'pt': 'pt-PT', 'ro': 'ro-RO',
    'ru': 'ru-RU', 'sr': 'sr-latn-RS', 'sk': 'sk-SK', 'sl': 'sl-SI', 'es': 'es-ES', 'sv': 'sv-SE', 'th': 'th-TH',
    'tr': 'tr-TR', 'uk': 'uk-UA', 'vi': 'vi-VN'
}

eol_array = [
    r'\. {0,}$', r'\! {0,}$', r'\? {0,}$', r'[\.\!\?\'] ?["”\'\)] {0,}$', u'\u2026 {0,}$',
    r'। {0,}$', r'。 {0,}$', r'？ {0,}$', r'！ {0,}$', r'։ {0,}$', r'۔ {0,}$', r'܁ {0,}$', r'܂ {0,}$',
    r'۔ {0,}$', r'᙮ {0,}$', r'᠃ {0,}$', r'᠉ {0,}$', r'⒈ {0,}$', r'⒉ {0,}$', r'⒊ {0,}$', r'⒋ {0,}$',
    r'⒌ {0,}$', r'⒍ {0,}$', r'⒎ {0,}$', r'⒏ {0,}$', r'⒐ {0,}$', r'⒑ {0,}$', r'⒒ {0,}$', r'⒓ {0,}$',
    r'⒔ {0,}$', r'⒕ {0,}$', r'⒖ {0,}$', r'⒗ {0,}$', r'⒘ {0,}$', r'⒙ {0,}$', r'⒚ {0,}$', r'⒛ {0,}$',
    r'⳹ {0,}$', r'⳾ {0,}$', r'⸼ {0,}$', r'꓿ {0,}$', r'꘎ {0,}$', r'꛳ {0,}$', r'︒ {0,}$', r'﹒ {0,}$',
    r'． {0,}$', r'｡ {0,}$', r'! {0,}$', r'¡ {0,}$', r'ǃ {0,}$', r'՜ {0,}$', r'߹ {0,}$', r'᥄ {0,}$',
    r'‼ {0,}$', r'⁈ {0,}$', r'❕ {0,}$', r'❗ {0,}$', r'❢ {0,}$', r'❣ {0,}$'
]

bol_array = [r'^[A-Z]']

line_separator_str = ' '
line_separator_nospace_str = '()'
line_separator_regex_str = r' ?\(\) ?'

TABLE_INDEX = 0
SOURCE_COL = 1
TRANSLATION_COL = 2
DEFAULT_MODEL = "gpt-5.4"

@dataclass
class TranslationConfig:
    """Configuration for the translation pipeline."""
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    max_translation_block_size: int = 100
    default_model: str = DEFAULT_MODEL
    reasoning_effort: str = "medium"  # options: "medium", "high", "xhigh"
    table_index: int = TABLE_INDEX
    source_col: int = SOURCE_COL
    translation_col: int = TRANSLATION_COL

    # Chunking options
    chunk_enabled: bool = False       # default OFF — entire file in one API call
    chunk_size: int = 100             # lines per chunk, used only if chunk_enabled=True

    # Language lists and tags
    google_translate_lang_codes: Dict[str, str] = field(default_factory=lambda: google_translate_lang_codes)
    right_to_left_languages_list: Dict[str, str] = field(default_factory=lambda: right_to_left_languages_list)
    shading_color_ignore_text: List[str] = field(default_factory=lambda: shading_color_ignore_text)
    office_language_tags: Dict[str, str] = field(default_factory=lambda: office_language_tags)

    # Patterns
    eol_array: List[str] = field(default_factory=lambda: eol_array)
    bol_array: List[str] = field(default_factory=lambda: bol_array)
