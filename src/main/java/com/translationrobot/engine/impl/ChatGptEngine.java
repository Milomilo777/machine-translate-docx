package com.translationrobot.engine.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.knuddels.jtokkit.Encodings;
import com.knuddels.jtokkit.api.Encoding;
import com.knuddels.jtokkit.api.EncodingRegistry;
import com.knuddels.jtokkit.api.EncodingType;
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

import java.math.BigDecimal;
import java.math.RoundingMode;

@Component
public class ChatGptEngine implements TranslationEngine {

    private static final EncodingRegistry REGISTRY = Encodings.newDefaultEncodingRegistry();
    private static final Encoding ENCODING = REGISTRY.getEncoding(EncodingType.CL100K_BASE);

    private final String apiKey;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;
    private String baseUrl = "https://api.openai.com";

    public ChatGptEngine(@Value("${openai.api.key:}") String apiKey) {
        this.apiKey = apiKey;
        this.restTemplate = new RestTemplate();
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.CHATGPT;
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();
        String prompt = PromptBuilderUtil.buildTranslationPrompt(sourceLang, targetLang, text);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(apiKey);

        ObjectNode requestBody = objectMapper.createObjectNode();
        requestBody.put("model", "gpt-4o"); // or whatever default model

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
                    baseUrl + "/v1/chat/completions",
                    entity,
                    String.class
            );

            JsonNode responseJson = objectMapper.readTree(response.getBody());
            String translatedText = responseJson.path("choices").get(0).path("message").path("content").asText();

            // Sanitize output
            translatedText = translatedText.replaceAll("\\n+", "\n");

            // Line Mismatch Check
            String[] inputLines = text.split("\n");
            String[] outputLines = translatedText.split("\n");
            if (inputLines.length != outputLines.length) {
                System.out.println("[WARNING] Line count mismatch! Input lines: " + inputLines.length + " vs Output lines: " + outputLines.length);
            }

            int inputTokens = responseJson.path("usage").path("prompt_tokens").asInt(0);
            int outputTokens = responseJson.path("usage").path("completion_tokens").asInt(0);
            String responseModel = responseJson.path("model").asText("");

            double totalCostUsd = calculateCost(responseModel, inputTokens, outputTokens);

            long endTime = System.currentTimeMillis();
            double executionTimeSec = (endTime - startTime) / 1000.0;

            return new TranslationResponse(translatedText, inputTokens, outputTokens, totalCostUsd, executionTimeSec);
        } catch (Exception e) {
            throw new RuntimeException("Error communicating with OpenAI API", e);
        }
    }

    public int estimateTokens(String text) {
        if (text == null) {
            return 0;
        }
        return ENCODING.countTokens(text);
    }

    private static final java.util.Map<String, Double[]> PRICES = java.util.Map.of(
            "gpt-5-pro", new Double[]{15.0, 120.0},
            "gpt-5.2", new Double[]{1.25, 10.00},
            "gpt-5.1", new Double[]{1.25, 10.00},
            "gpt-5", new Double[]{1.25, 10.00},
            "gpt-5-mini", new Double[]{0.25, 2.00},
            "gpt-5-nano", new Double[]{0.05, 0.40},
            "gpt-4o", new Double[]{2.50, 10.00},
            "gpt-4o-mini", new Double[]{0.15, 0.60} // Map.of supports up to 10 pairs, this is 8 pairs, so it's fine.
    );

    private double calculateCost(String model, int promptTokens, int completionTokens) {
        Double[] price = null;
        for (java.util.Map.Entry<String, Double[]> entry : PRICES.entrySet()) {
            if (model.contains(entry.getKey())) {
                price = entry.getValue();
                break;
            }
        }

        if (price == null) {
            System.out.println("[WARN] No known pricing for model '" + model + "'. Cost will be set to 0.");
            return 0.0;
        }

        double inputCost = (promptTokens / 1_000_000.0) * price[0];
        double outputCost = (completionTokens / 1_000_000.0) * price[1];

        double totalCost = inputCost + outputCost;
        return BigDecimal.valueOf(totalCost).setScale(6, RoundingMode.HALF_UP).doubleValue();
    }
}
