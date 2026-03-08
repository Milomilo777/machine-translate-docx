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

        // Unofficial Free DeepL Web Endpoint structure (mimicking frontend requests)
        // Warning: these endpoints may break; consider using an unofficial library if stability is needed.
        String url = "https://www2.deepl.com/jsonrpc?method=LMT_handle_texts";

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Content-Type", "application/json");
            headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

            // Extremely simplified approximation of the internal JSON-RPC payload
            // used by DeepL's web interface. Real implementation often requires complex hashing (like `id` and `timestamp`).
            int id = (int) (Math.random() * 100000000);
            String requestBody = String.format("{\"jsonrpc\":\"2.0\",\"method\":\"LMT_handle_texts\",\"id\":%d,\"params\":{\"texts\":[{\"text\":\"%s\",\"requestAlternatives\":3}],\"lang\":{\"target_lang\":\"%s\",\"source_lang_user_selected\":\"%s\"}}}",
                    id, text.replace("\"", "\\\"").replace("\n", "\\n"), targetLang.toUpperCase(), sourceLang.toUpperCase());

            HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);

            ResponseEntity<String> responseEntity = restTemplate.postForEntity(url, entity, String.class);
            JsonNode root = objectMapper.readTree(responseEntity.getBody());

            String translatedText = "";
            if (root.has("result") && root.get("result").has("texts") && root.get("result").get("texts").isArray()) {
                 translatedText = root.get("result").get("texts").get(0).get("text").asText();
            } else {
                 throw new RuntimeException("Unexpected response structure: " + responseEntity.getBody());
            }

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            return new TranslationResponse(translatedText, 0, 0, 0.0, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with free DeepL Web API: " + e.getMessage(), e);
        }
    }
}
