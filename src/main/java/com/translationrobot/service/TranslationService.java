package com.translationrobot.service;

import com.translationrobot.model.Translation;
import com.translationrobot.model.enums.TranslationEngineType;
import java.util.List;
import java.util.UUID;

/**
 * Service interface for managing translation-related business logic.
 */
public interface TranslationService {

    /**
     * Saves a new translation record associated with a specific document.
     *
     * @param documentId The UUID of the document the translation belongs to.
     * @param sourceText The original text that was translated.
     * @param translatedText The text after translation.
     * @param engine The translation engine used.
     * @throws com.translationrobot.exception.EntityNotFoundException if the document with the given ID is not found.
     */
    void saveTranslation(UUID documentId, String sourceText, String translatedText, TranslationEngineType engine);

    /**
     * Retrieves all translation records for a given document.
     *
     * @param documentId The UUID of the document.
     * @return A list of translations associated with the document. Returns an empty list if no translations are found.
     */
    List<Translation> getTranslationsByDocument(UUID documentId);
}
