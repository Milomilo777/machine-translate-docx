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
public class DeepLEngine implements TranslationEngine {

    private final String apiKey;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public DeepLEngine(@Value("${deepl.api.key:}") String apiKey) {
        this.apiKey = apiKey;
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.DEEPL;
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();

        String url = "https://api-free.deepl.com/v2/translate"; // Note: change to api.deepl.com for pro

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "DeepL-Auth-Key " + apiKey);
        headers.set("Content-Type", "application/json");

        String requestBody = String.format("{\"text\":[\"%s\"], \"source_lang\":\"%s\", \"target_lang\":\"%s\"}",
                                           text.replace("\"", "\\\"").replace("\n", "\\n"),
                                           sourceLang.toUpperCase(),
                                           targetLang.toUpperCase());

        HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);

        try {
            ResponseEntity<String> responseEntity = restTemplate.postForEntity(url, entity, String.class);
            JsonNode root = objectMapper.readTree(responseEntity.getBody());
            String translatedText = root.path("translations").get(0).path("text").asText();

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            // DeepL pricing is per character, dummy token values here
            return new TranslationResponse(translatedText, 0, 0, 0.0, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with DeepL API", e);
        }
    }
}
