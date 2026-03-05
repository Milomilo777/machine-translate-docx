package com.translationrobot.engine.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class GoogleEngine implements TranslationEngine {

    private final String apiKey;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public GoogleEngine(@Value("${google.api.key:}") String apiKey) {
        this.apiKey = apiKey;
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.GOOGLE;
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();

        String url = "https://translation.googleapis.com/language/translate/v2?key=" + apiKey;

        try {
            // Simplified for demonstration. In a real scenario, proper URL encoding and JSON body building are required.
            // Using a simple POST with JSON payload for v2 API
            String requestBody = String.format("{\"q\":\"%s\", \"source\":\"%s\", \"target\":\"%s\", \"format\":\"text\"}",
                                               text.replace("\"", "\\\"").replace("\n", "\\n"), sourceLang, targetLang);

            ResponseEntity<String> responseEntity = restTemplate.postForEntity(url, requestBody, String.class);
            JsonNode root = objectMapper.readTree(responseEntity.getBody());
            String translatedText = root.path("data").path("translations").get(0).path("translatedText").asText();

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            // Google Cloud Translation API pricing is typically per character, not token, but we set 0s for parity if tokens are unavailable
            return new TranslationResponse(translatedText, 0, 0, 0.0, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with Google Translate API", e);
        }
    }
}
