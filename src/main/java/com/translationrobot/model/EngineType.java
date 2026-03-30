package com.translationrobot.model;

public enum EngineType {
    GOOGLE,
    DEEPL,
    CHATGPT_API,
    CHATGPT_WEB,
    PERPLEXITY_WEB,
    YANDEX,
    GOOGLE_API,
    DEEPL_API;

    public static EngineType fromString(String text) {
        if (text == null) {
            throw new IllegalArgumentException("Unknown engine: null");
        }

        String normalized = text.trim().toLowerCase();

        return switch (normalized) {
            case "google" -> GOOGLE;
            case "deepl" -> DEEPL;
            case "chatgpt-api", "chatgpt_api" -> CHATGPT_API;
            case "chatgpt-web", "chatgpt_web" -> CHATGPT_WEB;
            case "chatgpt" -> CHATGPT_API;
            case "perplexity-web", "perplexity_web" -> PERPLEXITY_WEB;
            case "perplexity" -> PERPLEXITY_WEB;
            case "yandex" -> YANDEX;
            case "google-api", "google_api" -> GOOGLE_API;
            case "deepl-api", "deepl_api" -> DEEPL_API;
            default -> throw new IllegalArgumentException("Unknown engine: " + text);
        };
    }
}
