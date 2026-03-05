package com.translationrobot.engine.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class PerplexityEngine implements TranslationEngine {

    private final String apiKey;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public PerplexityEngine(@Value("${perplexity.api.key:}") String apiKey) {
        this.apiKey = apiKey;
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.PERPLEXITY;
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();
        String prompt = PromptBuilderUtil.buildTranslationPrompt(sourceLang, targetLang, text);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(apiKey);

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("model", "llama-3.1-sonar-large-128k-online"); // Example Perplexity model

        ArrayNode messages = requestBody.putArray("messages");

        ObjectNode systemMessage = messages.addObject();
        systemMessage.put("role", "system");
        systemMessage.put("content", "You are a professional subtitling translator.");

        ObjectNode userMessage = messages.addObject();
        userMessage.put("role", "user");
        userMessage.put("content", prompt);

        HttpEntity<String> entity = new HttpEntity<>(requestBody.toString(), headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(
                    "https://api.perplexity.ai/chat/completions",
                    entity,
                    String.class
            );

            JsonNode responseJson = objectMapper.readTree(response.getBody());
            String translatedText = responseJson.path("choices").get(0).path("message").path("content").asText();

            int inputTokens = responseJson.path("usage").path("prompt_tokens").asInt(0);
            int outputTokens = responseJson.path("usage").path("completion_tokens").asInt(0);

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            return new TranslationResponse(translatedText, inputTokens, outputTokens, 0.0, executionTimeSec); // Pricing not modeled
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with Perplexity API", e);
        }
    }
}
