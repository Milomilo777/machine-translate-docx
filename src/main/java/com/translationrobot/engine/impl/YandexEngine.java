package com.translationrobot.engine.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class YandexEngine implements TranslationEngine {

    // DISABLED ENGINE — Preserved for future use.
    // To re-enable: set ENABLED = true
    private static final boolean ENABLED = false;

    private final String apiKey;
    private final String folderId;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public YandexEngine(@Value("${yandex.api.key:}") String apiKey,
                        @Value("${yandex.folder.id:}") String folderId) {
        this.apiKey = apiKey;
        this.folderId = folderId;
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.YANDEX;
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        if (!ENABLED) {
            throw new UnsupportedOperationException(
                "Yandex engine is preserved but disabled in this build.");
        }
        long startTime = System.currentTimeMillis();

        String url = "https://translate.api.cloud.yandex.net/translate/v2/translate";

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Api-Key " + apiKey);
        headers.set("Content-Type", "application/json");

        String requestBody = String.format("{\"folderId\":\"%s\", \"texts\":[\"%s\"], \"sourceLanguageCode\":\"%s\", \"targetLanguageCode\":\"%s\"}",
                                           folderId,
                                           text.replace("\"", "\\\"").replace("\n", "\\n"),
                                           sourceLang,
                                           targetLang);

        HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);

        try {
            ResponseEntity<String> responseEntity = restTemplate.postForEntity(url, entity, String.class);
            JsonNode root = objectMapper.readTree(responseEntity.getBody());
            String translatedText = root.path("translations").get(0).path("text").asText();

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            return new TranslationResponse(translatedText, 0, 0, 0.0, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with Yandex API", e);
        }
    }
}
