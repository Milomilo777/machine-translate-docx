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
import org.springframework.web.client.HttpStatusCodeException;

import java.util.concurrent.ThreadLocalRandom;

@Component
public class GoogleEngine implements TranslationEngine {

    private static final java.util.concurrent.Semaphore RATE_LIMITER = new java.util.concurrent.Semaphore(1);

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
        try {
            RATE_LIMITER.acquire();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Thread interrupted while waiting for rate limiter", e);
        }

        try {
            long startTime = System.currentTimeMillis();

            int attempts = 0;
            TranslationResponse result = null;

            while (attempts < 3) {
                antiBot();
                try {
                    String url = String.format("https://translate.googleapis.com/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t",
                            sourceLang, targetLang);

                    org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
                    headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36");
                    headers.setContentType(org.springframework.http.MediaType.APPLICATION_FORM_URLENCODED);

                    org.springframework.util.MultiValueMap<String, String> map = new org.springframework.util.LinkedMultiValueMap<>();
                    map.add("q", text);

                    org.springframework.http.HttpEntity<org.springframework.util.MultiValueMap<String, String>> entity = new org.springframework.http.HttpEntity<>(map, headers);

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

                    StringBuilder translatedText = new StringBuilder();
                    if (root.isArray() && root.get(0).isArray()) {
                        for (JsonNode phraseNode : root.get(0)) {
                            translatedText.append(phraseNode.get(0).asText());
                        }
                    }

                    long endTime = System.currentTimeMillis();
                    double executionTimeSec = (endTime - startTime) / 1000.0;

                    result = new TranslationResponse(translatedText.toString(), 0, 0, 0.0, executionTimeSec);
                    break;
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                } catch (Exception e) {
                    // If it's not a 429/503 HTTP exception, we might still want to retry or throw.
                    // However, the instructions state: "get response code using whatever method this engine uses. if (responseCode == 429 || 503) { Thread.sleep(45000); attempts++; continue; }"
                    // We've handled 429/503 inside the inner try/catch for HttpStatusCodeException.
                    throw new RuntimeException("Error communicating with free Google Translate API: " + e.getMessage(), e);
                }
            }

            if (attempts >= 3) {
                throw new RuntimeException("Google Translate blocked after 3 retries");
            }

            return result;
        } finally {
            RATE_LIMITER.release();
        }
    }
}
