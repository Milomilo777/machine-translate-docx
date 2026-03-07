package com.translationrobot.engine;

import com.translationrobot.engine.impl.ChatGptEngine;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

class CostMathPropertyTest {

    @Property
    boolean costIsAlwaysValid(@ForAll int inTokens, @ForAll int outTokens) {
        ChatGptEngine engine = new ChatGptEngine("dummy");

        assertDoesNotThrow(() -> {
            ReflectionTestUtils.invokeMethod(engine, "calculateCost", "gpt-4o", inTokens, outTokens);
        });

        return true;
    }
}
