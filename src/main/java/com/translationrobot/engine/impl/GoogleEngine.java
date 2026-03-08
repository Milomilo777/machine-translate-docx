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

        try {
            String url = String.format("https://translate.googleapis.com/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t",
                    sourceLang, targetLang);

            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_FORM_URLENCODED);

            org.springframework.util.MultiValueMap<String, String> map = new org.springframework.util.LinkedMultiValueMap<>();
            map.add("q", text);

            org.springframework.http.HttpEntity<org.springframework.util.MultiValueMap<String, String>> entity = new org.springframework.http.HttpEntity<>(map, headers);

            ResponseEntity<String> responseEntity = restTemplate.postForEntity(url, entity, String.class);
            JsonNode root = objectMapper.readTree(responseEntity.getBody());

            StringBuilder translatedText = new StringBuilder();
            if (root.isArray() && root.get(0).isArray()) {
                for (JsonNode phraseNode : root.get(0)) {
                    translatedText.append(phraseNode.get(0).asText());
                }
            }

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            return new TranslationResponse(translatedText.toString(), 0, 0, 0.0, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with free Google Translate API: " + e.getMessage(), e);
        }
    }
}
