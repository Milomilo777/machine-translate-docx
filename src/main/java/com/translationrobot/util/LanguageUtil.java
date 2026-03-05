package com.translationrobot.util;

import java.util.Set;

public class LanguageUtil {

    private static final Set<String> RTL_LANGUAGES = Set.of("fa", "ar", "he", "ur", "ku", "am", "az");

    private static final Set<String> IGNORE_SET = Set.of(
            "-", ".", " ", ":", "!", "?", "...", "—", "•", "–", "»", "«", "“", "”", "‘", "’",
            "„", "‚", "‹", "›", "(", ")", "[", "]", "{", "}", "<", ">", "/", "\\", "|", "@",
            "#", "$", "%", "^", "&", "*", "+", "=", "~", "`", ";", "'", "\"", ",", "_"
    );

    public static boolean isRtlLanguage(String langCode) {
        if (langCode == null) {
            return false;
        }
        return RTL_LANGUAGES.contains(langCode.toLowerCase());
    }

    public static boolean isIgnoredText(String text) {
        if (text == null || text.isEmpty()) {
            return true;
        }
        return IGNORE_SET.contains(text.trim());
    }
}
