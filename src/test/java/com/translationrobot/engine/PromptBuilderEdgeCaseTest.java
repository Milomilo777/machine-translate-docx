package com.translationrobot.engine;

import com.translationrobot.engine.impl.PromptBuilderUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PromptBuilderEdgeCaseTest {

    @Test
    void buildPromptWithMassiveText_ShouldNotCrash() {
        StringBuilder massiveTextBuilder = new StringBuilder();
        for (int i = 0; i < 10000; i++) {
            massiveTextBuilder.append("word ").append(i).append("\n");
        }

        String prompt = PromptBuilderUtil.buildTranslationPrompt("en", "persian", massiveTextBuilder.toString());

        assertNotNull(prompt);
        assertTrue(prompt.contains("<ID> [THINK_LANG]: فارسی </ID>"));
        assertTrue(prompt.contains("<SMTV></SMTV>"));
    }
}
