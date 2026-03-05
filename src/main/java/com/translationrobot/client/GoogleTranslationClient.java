package com.translationrobot.client;

import com.translationrobot.exception.TranslationApiException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.Collections;
import java.util.Map;
import java.util.Random;

@Service
public class GoogleTranslationClient implements TranslationClient {

    private final RestTemplate restTemplate;
    private final Random random = new Random();

    // In a real scenario, this URL should be configurable and point to a valid Google Translate API endpoint.
    // For demonstration, it's a placeholder.
    @Value("${translation.api.google.url:http://localhost:8080/mock-google-translate}")
    private String googleApiUrl;

    @Value("${translation.api.key}") // Requirement: Externalize the API Key
    private String apiKey;

    public GoogleTranslationClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @Override
    public String translate(String sourceText, String sourceLang, String targetLang) throws TranslationApiException {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(Collections.singletonList(MediaType.APPLICATION_JSON));

        // This structure simulates a generic translation API request body.
        // Google Translate API's actual request body might vary (e.g., for batch requests, different versions).
        Map<String, Object> requestBody = Map.of(
            "q", sourceText,
            "source", sourceLang,
            "target", targetLang,
            "key", apiKey // API key is often a query parameter, but shown here as part of body for simplicity.
        );

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);

        try {
            System.out.println("DEBUG: Simulating API call for translation: '" + sourceText + "' (" + sourceLang + " -> " + targetLang + ")");

            // Simulate network latency (100-500ms)
            Thread.sleep(100 + random.nextInt(400));

            // Simulate occasional API errors (e.g., timeout, service unavailable)
            if (random.nextDouble() < 0.05) { // 5% chance of simulating a service unavailability
                throw new HttpClientErrorException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE, "Simulated Google API Service Unavailable");
            }
            if (random.nextDouble() < 0.02) { // 2% chance of simulating a timeout/network issue
                 throw new ResourceAccessException("Simulated Google API Timeout (Connection refused)");
            }

            // In a real scenario, you'd make the actual HTTP call:
            // ResponseEntity<Map> response = restTemplate.postForEntity(googleApiUrl, entity, Map.class);
            // Example of parsing a hypothetical response structure:
            // List<Map<String, String>> translations = (List<Map<String, String>>) ((Map) response.getBody().get("data")).get("translations");
            // return translations.get(0).get("translatedText");

            // For this implementation, we return a mock translated text.
            return "translated(" + targetLang + "): " + sourceText;

        } catch (HttpClientErrorException e) {
            // Catches HTTP status errors (e.g., 4xx, 5xx from the API)
            System.err.println("Google Translation API returned an HTTP error: " + e.getStatusCode() + " - " + e.getResponseBodyAsString());
            throw new TranslationApiException("Google Translation API HTTP error: " + e.getMessage(), e);
        } catch (ResourceAccessException e) {
            // Catches network errors, connection timeouts, etc.
            System.err.println("Network/Resource error communicating with Google Translation API: " + e.getMessage());
            throw new TranslationApiException("Google Translation API timeout or network issue: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt(); // Restore the interrupted status
            System.err.println("Translation API call interrupted: " + e.getMessage());
            throw new TranslationApiException("Translation API call interrupted: " + e.getMessage(), e);
        } catch (Exception e) {
            // Catch any other unexpected errors
            System.err.println("An unexpected error occurred during Google Translation: " + e.getMessage());
            throw new TranslationApiException("An unexpected error occurred during Google Translation: " + e.getMessage(), e);
        }
    }

    @Override
    public String getEngineType() {
        return "GOOGLE"; // Tracking: engineType
    }
}
