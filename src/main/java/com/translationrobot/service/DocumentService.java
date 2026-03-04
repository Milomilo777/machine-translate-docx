package com.translationrobot.service;

import com.translationrobot.model.Document;
import com.translationrobot.model.enums.DocumentStatus;
import java.util.List;
import java.util.UUID;

/**
 * Service interface for managing document-related business logic.
 */
public interface DocumentService {

    /**
     * Saves a new document or updates an existing one.
     *
     * @param document The document entity to save.
     * @return The saved or updated document entity.
     */
    Document saveDocument(Document document);

    /**
     * Retrieves a document by its unique identifier.
     *
     * @param id The UUID of the document.
     * @return The document entity.
     * @throws com.translationrobot.exception.EntityNotFoundException if the document is not found.
     */
    Document getDocumentById(UUID id);

    /**
     * Updates the status of a specific document.
     *
     * @param id The UUID of the document to update.
     * @param newStatus The new status to set for the document.
     * @return The updated document entity.
     * @throws com.translationrobot.exception.EntityNotFoundException if the document is not found.
     */
    Document updateDocumentStatus(UUID id, DocumentStatus newStatus);

    /**
     * Retrieves a list of documents that are in 'UPLOADED' status,
     * indicating they are pending processing or translation.
     *
     * @return A list of documents with 'UPLOADED' status.
     */
    List<Document> getPendingDocuments();
}
