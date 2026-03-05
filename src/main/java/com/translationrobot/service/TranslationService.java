package com.translationrobot.service;

import java.util.UUID;

public interface TranslationService {
    /**
     * Initiates an asynchronous translation process for a given document.
     * @param documentId The ID of the document to process.
     */
    void processDocument(UUID documentId);
}
