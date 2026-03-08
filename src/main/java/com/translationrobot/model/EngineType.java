package com.translationrobot.model;

public enum EngineType {
    GOOGLE, DEEPL, YANDEX, CHATGPT, PERPLEXITY;

    public static EngineType fromString(String text) {
        if (text == null) return null;
        String normalized = text.trim().toUpperCase();
        if (normalized.contains("CHATGPT")) {
            return CHATGPT;
        } else if (normalized.contains("DEEPL")) {
            return DEEPL;
        } else if (normalized.contains("GOOGLE")) {
            return GOOGLE;
        } else if (normalized.contains("PERPLEXITY")) {
            return PERPLEXITY;
        } else if (normalized.contains("YANDEX")) {
            return YANDEX;
        }
        throw new IllegalArgumentException("Unknown translation engine: " + text);
    }
}
