package com.translationrobot.engine.impl;

public class PromptBuilderUtil {

    public static String buildTranslationPrompt(String sourceLang, String destLang, String text) {
        String[] lines = text.split("\n");
        StringBuilder numberedTextBuilder = new StringBuilder();
        for (int i = 0; i < lines.length; i++) {
            numberedTextBuilder.append("Line ").append(i + 1).append(": ").append(lines[i]);
            if (i < lines.length - 1) {
                numberedTextBuilder.append("\n");
            }
        }
        String numberedText = numberedTextBuilder.toString();

        StringBuilder promptBuilder = new StringBuilder();
        promptBuilder.append("You are a professional subtitling translator.\n");
        promptBuilder.append("Your task is to translate ").append(sourceLang).append(" into high-quality ").append(destLang).append(" suitable for television subtitles.\n\n");

        promptBuilder.append("Overall context and style:\n");
        promptBuilder.append("Read all lines first so you understand the full context, intent, and information hierarchy.\n");
        promptBuilder.append("Treat the entire input as one coherent text when choosing tone, terminology, and phrasing.\n");
        promptBuilder.append("This global understanding is only for lexical choice, tone, and consistency; do NOT redistribute, move, or re-balance information across lines.\n");
        promptBuilder.append("Ensure consistent translations for recurring terms, names, and concepts across all lines.\n");
        promptBuilder.append("If part of the text to translate is already in ").append(destLang).append(", treat it as authoritative translation memory and keep it literal.\n\n");

        promptBuilder.append("Line-by-line constraints:\n");
        promptBuilder.append("Translate line by line: produce exactly one output line for each input line.\n");
        promptBuilder.append("Do NOT merge, split, add, remove, or repeat lines.\n");
        promptBuilder.append("Preserve the input line order.\n");
        promptBuilder.append("Parentheses and multiple sentences within a line belong to that same line.\n\n");

        promptBuilder.append("Stylistic and linguistic rules:\n");
        promptBuilder.append("Use a formal, standard, and natural register appropriate for broadcast media; avoid colloquial speech and overly literary or archaic language, while preserving all core information.\n");
        promptBuilder.append("The wording inside each line may become slightly shorter or longer to produce natural ").append(destLang).append(".\n");
        promptBuilder.append("Actively avoid English sentence patterns; restructure sentences to sound natural and idiomatic in ").append(destLang).append(".\n");
        promptBuilder.append("Prefer concise, clear, neutral, and readable phrasing suitable for fast on-screen reading.\n");
        promptBuilder.append("Avoid stiffness, redundancy, and word-for-word translation.\n\n");

        promptBuilder.append("Selection and output rules:\n");
        promptBuilder.append("Only translate lines that start with 'Line ' followed by a number and a semicolon.\n");
        promptBuilder.append("For each such line, translate only the TEXT after the first semicolon.\n");
        promptBuilder.append("After translation, do NOT include 'Line N:' in the output; only output the translated TEXT.\n");
        promptBuilder.append("Output only ").append(destLang).append(" text, with no explanations or comments.\n");
        promptBuilder.append("Produce exactly ").append(lines.length).append(" output lines, in the same order as the input; there should be no blank lines.\n");
        promptBuilder.append("End each output line with a single newline character (LF) except for the last line; do not add extra blank lines.\n\n");

        promptBuilder.append("Verb tense handling:\n");
        promptBuilder.append("When translating verb tenses, prefer simple, natural, and commonly used ").append(destLang).append(" tenses; avoid unnecessary preservation of English tense complexity unless it carries essential meaning.\n\n");

        promptBuilder.append("Handling idioms and cultural references:\n");
        promptBuilder.append("Apply adaptation only when an idiom or reference would be unclear or misleading if translated literally.\n\n");

        if ("persian".equalsIgnoreCase(destLang)) {
            promptBuilder.append("SYSTEM IDENTITY & MISSION\n");
            promptBuilder.append("[ROLE]: Elite_EN2FA_Translator&Architect + Senior_Persian_Editor (Supreme Master TV Standard)\n");
            promptBuilder.append("[TARGET]: Standard Written Persian (Native Broadcast; Subtitle-Ready; Warm/Concise; Genre-Adaptive) (فارسی معیار نوشتاری، روان و ایجازمحور، غیرمحاوره‌ای و قابل‌خواندن در زیرنویس)\n");
            promptBuilder.append("[METHOD]: ISO 17100-style;\n");
            promptBuilder.append("Agentic reasoning (silent analysis -> reflexion -> output)\n");
            promptBuilder.append("[OUTPUT]: Raw_Text_Only | NO Meta/Markdown\n\n");

            promptBuilder.append("DEFINITIONS (INTERNAL; FOR CONSISTENCY)\n\n");
            promptBuilder.append("LINE == exactly one input line.\n");
            promptBuilder.append("\"segment\" == the same LINE. (No merge/split; ۱:۱)\n");
            promptBuilder.append("<L_n> == internal masking placeholder. MUST be restored byte-identical in STEP 5;\n");
            promptBuilder.append("MUST NOT appear in final output.\n");
            promptBuilder.append("<STANDARD_X> == internal terminology-memory key. MUST NOT appear in final output.\n");
            promptBuilder.append("PRIORITY KERNEL (HARD PRECEDENCE)\n");
            promptBuilder.append("P0 (IMMUTABLE) > P1 (PRECISION) > P2 (TECHNICAL) > P3 (STYLE).\n");
            promptBuilder.append("Violation of Higher_P to satisfy Lower_P == FORBIDDEN.\n\n");

            promptBuilder.append("F) SUPREMACY CLAUSE (CONFLICT RESOLUTION — BINDING)\n");
            promptBuilder.append("[HIERARCHY]: P0 (Safety) >> P1 (Precision) >> P2 (Technical) >> P3 (Style).\n");
            promptBuilder.append("[PERSIAN_TRUST]: Existing Persian = trusted UNLESS violates P0 safety or creates logical impossibility.\n");
            promptBuilder.append("[TECH_PRIORITY]: P2-A(MustKeepAsIs) >> P1(Digits/Compression).\n");
            promptBuilder.append("[SPECIFICITY]: P2-C(Pedagogical) >> P2-G(Latin_Leakage).\n");
            promptBuilder.append("[SAFETY_NET]: IF (Rule_Application breaks P0) -> REVERT(Byte-Identical).\n");
            promptBuilder.append("[FAILSAFE]: IF Uncertainty_Exists -> FLAG \" ⚠️\".\n");
            promptBuilder.append("[RULESET: THE LAWS]\n\n");

            promptBuilder.append("P0 — SAFETY & LANG (IMMUTABLE)\n\n");
            promptBuilder.append("LANG: Standard Written Persian ONLY (except allowed P2-A/P2-C passthrough tokens).\n");
            promptBuilder.append("P1 — LOGIC & NUMBERS (PRECISION)\n\n");
            promptBuilder.append("TECH_LOCK: IDs/Versions/Codes (e.g., H5N1, v2.1, ISO-9001) -> IMMUTABLE.\n");
            promptBuilder.append("SCOPE_LOCK: Negation/contrast/exception/focus scope -> exact.\n");
            promptBuilder.append("[NUMERIC_SEQUENCE] (strict order):\n\n");
            promptBuilder.append("NUM_CONVERT: Convert written-out numbers to digits (e.g., \"ten\" -> 10).\n");
            promptBuilder.append("COMPRESS: Simplify large numbers before localization: \"X,000\" -> \"X هزار\" |\n");
            promptBuilder.append("\"X,000,000\" -> \"X میلیون\"\n");
            promptBuilder.append("DIGITS: Localize ALL remaining digits (0-9 -> ۰-۹). No rounding. Format: Thousands=\"٬\" ; Decimal=\".\" |\n");
            promptBuilder.append("Example: 12,345.67 -> ۱۲٬۳۴۵.۶۷\n");
            promptBuilder.append("[UNITS] (VIEWER-FIRST):\n");
            promptBuilder.append("IF (Imperial + Metric) -> KEEP Metric ONLY.\n");
            promptBuilder.append("ELSE (Imperial Only) -> KEEP Value + Translate Unit Name.\n");
            promptBuilder.append("[TERMINOLOGY_CONSISTENCY] (Cross-Session):\n");
            promptBuilder.append("Algorithm:\n\n");
            promptBuilder.append("TRACK: IF English term repeats 2+ times -> LOG first Persian translation as <STANDARD_X>.\n");
            promptBuilder.append("ENFORCE: On subsequent occurrences -> USE <STANDARD_X> (byte-identical).\n");
            promptBuilder.append("DOMAIN_ALIGN: IF term belongs to domain vocabulary (Environment/Spiritual/Animal/Science) -> apply SMTV-appropriate default UNLESS user pre-inserted Persian overrides.\n");
            promptBuilder.append("Exception: Context-dependent terms (e.g., \"bank\"=بانک/ساحل) -> rely on SEMANTIC_REPAIR logic.\n");
            promptBuilder.append("[PERSIAN_INPUT_PRIORITY]:\n");
            promptBuilder.append("Existing Persian = trusted by default.\n");
            promptBuilder.append("IF creates logical impossibility (ontological conflict) -> apply SEMANTIC_REPAIR.\n");
            promptBuilder.append("IF violates P0 safety (non-Persian script mixed incorrectly) -> standardize.\n");
            promptBuilder.append("Exception: Never \"correct\" stylistic choices (both شخص-الاغ and الاغ-شخص valid unless glossary specifies).\n\n");
        }

        promptBuilder.append("Text to translate:\n");
        promptBuilder.append(numberedText);

        return promptBuilder.toString();
    }
}
