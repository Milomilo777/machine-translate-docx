package com.translationrobot.engine.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import java.util.concurrent.ThreadLocalRandom;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpStatusCodeException;

@Component
public class DeepLEngine implements TranslationEngine {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public DeepLEngine() {
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.DEEPL;
    }

    private void antiBot() {
        try {
            long ms = 2000 + ThreadLocalRandom.current().nextLong(3000);
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();

        int attempts = 0;
        TranslationResponse result = null;

        while (attempts < 3) {
            antiBot();
            try {
                // Unofficial Free DeepL Web Endpoint structure (mimicking frontend requests)
                String url = "https://www2.deepl.com/jsonrpc";

                HttpHeaders headers = new HttpHeaders();
                headers.set("Content-Type", "application/json");
                headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36");

                String requestBody = String.format("{\"jsonrpc\":\"2.0\",\"method\":\"LMT_handle_texts\",\"params\":{\"texts\":[{\"text\":\"%s\"}],\"lang\":{\"source_lang_user_selected\":\"%s\",\"target_lang\":\"%s\"}}}",
                        text.replace("\"", "\\\"").replace("\n", "\\n"), sourceLang.toUpperCase(), targetLang.toUpperCase());

                HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);

                ResponseEntity<String> responseEntity;
                try {
                    responseEntity = restTemplate.postForEntity(url, entity, String.class);
                } catch (HttpStatusCodeException httpException) {
                    int responseCode = httpException.getStatusCode().value();
                    if (responseCode == 429 || responseCode == 503) {
                        Thread.sleep(45000);
                        attempts++;
                        continue;
                    }
                    throw httpException;
                }

                JsonNode root = objectMapper.readTree(responseEntity.getBody());

                String translatedText = "";
                if (root.has("result") && root.get("result").has("texts") && root.get("result").get("texts").isArray()) {
                     translatedText = root.get("result").get("texts").get(0).get("text").asText();
                } else {
                     throw new RuntimeException("Unexpected response structure: " + responseEntity.getBody());
                }

                long endTime = System.currentTimeMillis();
                double executionTimeSec = (endTime - startTime) / 1000.0;

                result = new TranslationResponse(translatedText, 0, 0, 0.0, executionTimeSec);
                break;
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                throw new RuntimeException("Error communicating with free DeepL Web API: " + e.getMessage(), e);
            }
        }

        if (attempts >= 3) {
            throw new RuntimeException("DeepL blocked after 3 retries");
        }

        return result;
    }
}
// ===== DISABLED: DeepL Official Free API =====
// Endpoint: https://api-free.deepl.com/v2/translate
// Header:   Authorization: DeepL-Auth-Key YOUR_KEY_HERE
// Preserved for future use. Currently NOT active.
// =============================================
