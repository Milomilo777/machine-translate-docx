package com.translationrobot.util;

import net.jqwik.api.ForAll;
import net.jqwik.api.Property;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

class LanguagePropertyTest {

    @Property
    boolean rtlLogicNeverCrashes(@ForAll String randomString) {
        assertDoesNotThrow(() -> LanguageUtil.isRtlLanguage(randomString));
        assertDoesNotThrow(() -> LanguageUtil.isIgnoredText(randomString));
        return true;
    }
}
