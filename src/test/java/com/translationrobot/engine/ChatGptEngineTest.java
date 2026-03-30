package com.translationrobot.engine;

import com.translationrobot.engine.impl.ChatGptEngine;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ChatGptEngineTest {

    private ChatGptEngine chatGptEngine;

    @BeforeEach
    void setUp() {
        chatGptEngine = new ChatGptEngine("dummy-api-key");
    }

    @Test
    void testEstimateTokens_PersianText() {
        String persianText = "سلام دنیا! این یک تست برای شبکه SMTV است.";
        int tokenCount = chatGptEngine.estimateTokens(persianText);
        assertTrue(tokenCount > 0, "Token count should be greater than 0");
    }

    @Test
    void testCostCalculationMath_Gpt5_2() {
        int inputTokens = 1000;
        int outputTokens = 500;
        String modelName = "gpt-5.2-turbo";

        Double cost = ReflectionTestUtils.invokeMethod(chatGptEngine, "calculateCost", modelName, inputTokens, outputTokens);

        // Expected Cost: (1000 * 1.25 / 1000000) + (500 * 10.00 / 1000000) = 0.00125 + 0.005 = 0.00625
        assertEquals(0.00625, cost, 0.000001, "Cost calculation for gpt-5.2 is incorrect");
    }
}
