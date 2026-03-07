package com.translationrobot.service;

import com.translationrobot.engine.impl.PromptBuilderUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

class UnicodeAndTagIntegrityTest {

    @Test
    void testUnicodeAndTagsIntegrity() {
        // ZWNJ is \u200C
        String complexPersianText = "<ID:999>یک متن با نیم\u200Cفاصله</SMTV>";

        String prompt = PromptBuilderUtil.buildTranslationPrompt("en", "persian", complexPersianText);

        // Assert tags are preserved
        assertTrue(prompt.contains("<ID:999>"), "Should preserve the <ID> tag exactly");
        assertTrue(prompt.contains("</SMTV>"), "Should preserve the </SMTV> tag exactly");

        // Assert ZWNJ is preserved
        assertTrue(prompt.contains("نیم\u200Cفاصله"), "Should preserve the ZWNJ exactly");
    }
}
