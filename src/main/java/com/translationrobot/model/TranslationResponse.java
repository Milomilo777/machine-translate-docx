package com.translationrobot.model;

public record TranslationResponse(
        String translatedText,
        int inputTokens,
        int outputTokens,
        double totalCostUsd,
        double executionTimeSec
) {}
