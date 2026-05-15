"""Rich language descriptors for the universal-prompt JOB_CONFIG block.

The universal translate/polish prompts use generic ``source language`` /
``target language`` placeholders. The actual language identity is supplied in
the user message via ``<JOB_CONFIG>``. Putting the language info in the
user message — not the system prompt — keeps the system prompt byte-identical
across documents, which is the precondition for OpenAI prompt caching (the
first ≥1024 tokens of the prefix must match for cache to hit).

This module resolves a short language code (e.g. ``fa``, ``zh``, ``pt``)
into a richer human-readable descriptor. The descriptor names the language
in English, names it in its native script, and disambiguates variant/script
when relevant (Simplified vs Traditional Chinese, Brazilian vs European
Portuguese, MSA vs colloquial Arabic, etc.).

Why richer descriptors matter: GPT-5.5 noted that ``TARGET_LANGUAGE: FA``
is less discriminative than ``TARGET_LANGUAGE: Persian / فارسی, Iran,
modern standard written Persian``. The richer form binds the policy
unambiguously even when the short code might be parsed as something else
by a smaller model.
"""
from __future__ import annotations

# Curated descriptors. Keys are lower-case language codes (BCP-47 short
# form). Add new entries here when a new locale is on the regular run-list.
_DESCRIPTORS: dict[str, str] = {
    "en":     "English",
    "fa":     "Persian / فارسی, Iran, modern standard written Persian",
    "ar":     "Arabic / العربية, Modern Standard Arabic (MSA)",
    "es":     "Spanish / Español, modern standard",
    "fr":     "French / Français, modern standard",
    "de":     "German / Deutsch, modern standard",
    "it":     "Italian / Italiano, modern standard",
    "pt":     "Portuguese / Português, Brazilian by default unless source indicates European",
    "pt-br":  "Portuguese / Português (Brazilian), modern standard",
    "pt-pt":  "Portuguese / Português (European), modern standard",
    "tr":     "Turkish / Türkçe, modern standard",
    "ru":     "Russian / Русский, modern standard",
    "ja":     "Japanese / 日本語, modern standard (formal politeness, dignified TV register)",
    "ko":     "Korean / 한국어, modern standard (formal honorific TV register)",
    "zh":     "Chinese / 中文, Simplified (zh-Hans) unless source indicates Traditional",
    "zh-cn":  "Chinese / 中文, Simplified (zh-Hans)",
    "zh-tw":  "Chinese / 中文, Traditional (zh-Hant)",
    "vi":     "Vietnamese / Tiếng Việt, modern standard",
    "th":     "Thai / ภาษาไทย, modern standard",
    "id":     "Indonesian / Bahasa Indonesia, modern standard",
    "ms":     "Malay / Bahasa Melayu, modern standard",
    "tl":     "Tagalog / Wikang Tagalog, modern standard",
    "hi":     "Hindi / हिन्दी, modern standard",
    "ur":     "Urdu / اردو, modern standard",
    "bn":     "Bengali / বাংলা, modern standard",
    "ta":     "Tamil / தமிழ், modern standard",
    "te":     "Telugu / తెలుగు, modern standard",
    "lo":     "Lao / ພາສາລາວ, modern standard",
    "km":     "Khmer / ភាសាខ្មែរ, modern standard",
    "my":     "Burmese / မြန်မာဘာသာ, modern standard",
    "nl":     "Dutch / Nederlands, modern standard",
    "pl":     "Polish / Polski, modern standard",
    "uk":     "Ukrainian / Українська, modern standard",
    "ro":     "Romanian / Română, modern standard",
    "cs":     "Czech / Čeština, modern standard",
    "el":     "Greek / Ελληνικά, modern standard",
    "he":     "Hebrew / עברית, modern standard",
    "sv":     "Swedish / Svenska, modern standard",
    "no":     "Norwegian (Bokmål) / Norsk bokmål",
    "nb":     "Norwegian (Bokmål) / Norsk bokmål",
    "da":     "Danish / Dansk, modern standard",
    "fi":     "Finnish / Suomi, modern standard",
    "hu":     "Hungarian / Magyar, modern standard",
    "bg":     "Bulgarian / Български, modern standard",
    "sr":     "Serbian / Српски, Cyrillic (sr-Cyrl) unless source indicates Latin (sr-Latn)",
    "hr":     "Croatian / Hrvatski, modern standard",
    "sk":     "Slovak / Slovenčina, modern standard",
    "sl":     "Slovenian / Slovenščina, modern standard",
    "et":     "Estonian / Eesti, modern standard",
    "lv":     "Latvian / Latviešu, modern standard",
    "lt":     "Lithuanian / Lietuvių, modern standard",
    "ca":     "Catalan / Català, modern standard",
    "kk":     "Kazakh / Қазақ тілі, Cyrillic script",
    "az":     "Azerbaijani / Azərbaycan dili, Latin script",
    "ka":     "Georgian / ქართული, modern standard",
    "hy":     "Armenian / Հայերեն, modern standard (Eastern)",
    "mn":     "Mongolian / Монгол, Cyrillic script",
    "ne":     "Nepali / नेपाली, modern standard",
    "si":     "Sinhala / සිංහල, modern standard",
    "ml":     "Malayalam / മലയാളം, modern standard",
    "kn":     "Kannada / ಕನ್ನಡ, modern standard",
    "gu":     "Gujarati / ગુજરાતી, modern standard",
    "mr":     "Marathi / मराठी, modern standard",
    "pa":     "Punjabi / ਪੰਜਾਬੀ (Gurmukhi script) unless source indicates Shahmukhi",
    "sw":     "Swahili / Kiswahili, modern standard",
    "am":     "Amharic / አማርኛ, modern standard",
    "ha":     "Hausa, Latin script (Boko)",
    "yo":     "Yoruba / Yorùbá, modern standard",
    "zu":     "Zulu / isiZulu, modern standard",
    "af":     "Afrikaans, modern standard",
    "ku":     "Kurdish (Kurmanji by default unless source indicates Sorani)",
    "ckb":    "Kurdish (Sorani) / سۆرانی, Arabic script",
    "kmr":    "Kurdish (Kurmanji) / Kurmancî, Latin script",
    "ps":     "Pashto / پښتو, modern standard",
    "prs":    "Dari / دری, modern standard",
    "tg":     "Tajik / Тоҷикӣ, Cyrillic script",
    "uz":     "Uzbek / Oʻzbekcha, Latin script",
    "ky":     "Kyrgyz / Кыргызча, Cyrillic script",
    "ug":     "Uyghur / ئۇيغۇرچە, Arabic script",
    "bo":     "Tibetan / བོད་སྐད་, modern standard",
    "dv":     "Dhivehi / ދިވެހި, Thaana script",
}


def lang_descriptor(code: str | None) -> str:
    """Resolve *code* to a rich JOB_CONFIG-ready language descriptor.

    Falls back to the project-level ``google_translate_lang_codes`` mapping,
    then to the raw code, when the curated table has no entry. Callers can
    pass either a short code (``fa``), a region-qualified short code
    (``zh-cn``), or a longer string — the function does its best to find
    a useful descriptor.
    """
    if not code:
        return "Unknown"

    raw = str(code).strip()
    lower = raw.lower()

    # 1. Direct hit in curated table (with optional region).
    if lower in _DESCRIPTORS:
        return _DESCRIPTORS[lower]

    # 2. Region-qualified code: try the bare primary subtag.
    primary = lower.split("-")[0].split("_")[0]
    if primary in _DESCRIPTORS:
        return _DESCRIPTORS[primary]

    # 3. Fall back to the project's bulk lang-code → English-name table.
    try:
        from ..config import google_translate_lang_codes
        if lower in google_translate_lang_codes:
            return google_translate_lang_codes[lower]
        if primary in google_translate_lang_codes:
            return google_translate_lang_codes[primary]
    except Exception:
        pass

    # 4. Last resort: pass the raw code through unchanged. Better than
    #    silently returning "Unknown" — at least the model sees what the
    #    operator supplied.
    return raw
