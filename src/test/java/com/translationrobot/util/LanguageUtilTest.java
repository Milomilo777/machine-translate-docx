package com.translationrobot.util;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LanguageUtilTest {

    @Test
    void isIgnoredText_WithPunctuation_ShouldReturnTrue() {
        assertTrue(LanguageUtil.isIgnoredText("-"));
        assertTrue(LanguageUtil.isIgnoredText("..."));
        assertTrue(LanguageUtil.isIgnoredText("?"));
        assertTrue(LanguageUtil.isIgnoredText("!"));
        // The implementation checks if text.trim() is in the set, and "   " trims to "".
        // Our implementation of isIgnoredText returns true for text.isEmpty() (which "   " is after trim? No, it returns true if text is empty before trim, but "   " isn't empty before trim. Wait, "   ".trim() is "", which is not in IGNORE_SET. Let's look at the implementation.
        // Actually, if it's spaces, it's considered empty? The problem was "   ". Let's change the test to match the implementation, or fix the implementation. The issue says "blank text is skipped".
        assertTrue(LanguageUtil.isIgnoredText("   ")); // Test whitespace
        assertTrue(LanguageUtil.isIgnoredText("")); // Empty string
        assertTrue(LanguageUtil.isIgnoredText(null)); // Null
    }

    @Test
    void isIgnoredText_WithNormalWords_ShouldReturnFalse() {
        assertFalse(LanguageUtil.isIgnoredText("Hello"));
        assertFalse(LanguageUtil.isIgnoredText("سلام"));
        assertFalse(LanguageUtil.isIgnoredText("123"));
        assertFalse(LanguageUtil.isIgnoredText("Good morning!")); // Sentence with punctuation is not ignored
    }

    @Test
    void isRtlLanguage_WithRtlLanguages_ShouldReturnTrue() {
        assertTrue(LanguageUtil.isRtlLanguage("fa"));
        assertTrue(LanguageUtil.isRtlLanguage("FA")); // Test case insensitivity
        assertTrue(LanguageUtil.isRtlLanguage("ar"));
        assertTrue(LanguageUtil.isRtlLanguage("he"));
    }

    @Test
    void isRtlLanguage_WithLtrLanguages_ShouldReturnFalse() {
        assertFalse(LanguageUtil.isRtlLanguage("en"));
        assertFalse(LanguageUtil.isRtlLanguage("fr"));
        assertFalse(LanguageUtil.isRtlLanguage("es"));
        assertFalse(LanguageUtil.isRtlLanguage(""));
        assertFalse(LanguageUtil.isRtlLanguage(null));
    }
}
