package com.translationrobot.engine;

import com.github.tomakehurst.wiremock.junit5.WireMockTest;
import com.translationrobot.engine.impl.ChatGptEngine;
import com.translationrobot.model.TranslationResponse;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@WireMockTest(httpPort = 8089)
class OpenAiWireMockTest {

    @Test
    void testChatGptEngine_WithWireMock() {
        // Stub the OpenAI API response
        stubFor(post(urlEqualTo("/v1/chat/completions"))
                .willReturn(aResponse()
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"choices\": [{\"message\": {\"content\": \"سلام\"}}], \"usage\": {\"prompt_tokens\": 100, \"completion_tokens\": 50}, \"model\": \"gpt-4o\"}")));

        ChatGptEngine engine = new ChatGptEngine("dummy-key");
        ReflectionTestUtils.setField(engine, "baseUrl", "http://localhost:8089");

        TranslationResponse response = engine.translate("en", "fa", "Hello");

        assertNotNull(response);
        assertEquals("سلام", response.translatedText().trim());
        assertEquals(100, response.inputTokens());
        assertEquals(50, response.outputTokens());
    }
}
