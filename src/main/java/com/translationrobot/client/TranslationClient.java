package com.translationrobot.client;

import com.translationrobot.exception.TranslationApiException;

public interface TranslationClient {
    /**
     * Translates a given text segment from a source language to a target language.
     * @param sourceText The text segment to translate.
     * @param sourceLang The source language code (e.g., "en").
     * @param targetLang The target language code (e.g., "es").
     * @return The translated text.
     * @throws TranslationApiException if an error occurs during the translation process (e.g., API error, timeout).
     */
    String translate(String sourceText, String sourceLang, String targetLang) throws TranslationApiException;

    /**
     * Returns the type of translation engine used by this client.
     * @return The engine type string (e.g., "GOOGLE").
     */
    String getEngineType();
}
