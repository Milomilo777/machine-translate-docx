package com.translationrobot.controller.v1;

import com.translationrobot.dto.DocumentRequestDTO;
import com.translationrobot.model.Document;
import com.translationrobot.model.DocumentStatus;
import com.translationrobot.model.Translation;
import com.translationrobot.service.DocumentService;
import com.translationrobot.service.TranslationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.List;

/**
 * REST Controller for managing document translation requests.
 * Implements version 1 of the API.
 */
@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor // Lombok for constructor injection of final fields
public class DocumentController {

    private final DocumentService documentService;
    private final TranslationService translationService;

    // If Lombok is not used, replace @RequiredArgsConstructor with:
    // public DocumentController(DocumentService documentService, TranslationService translationService) {
    //     this.documentService = documentService;
    //     this.translationService = translationService;
    // }

    /**
     * POST /api/v1/documents
     * Creates a new document translation request.
     * Accepts a validated DocumentRequestDTO and returns the created Document with a Location header.
     * @param documentRequestDTO The DTO containing details for the new document.
     * @param ucb UriComponentsBuilder for constructing the Location header.
     * @return ResponseEntity with status 201 Created, the saved Document, and a Location header.
     */
    @PostMapping
    public ResponseEntity<Document> createDocument(
            @Valid @RequestBody DocumentRequestDTO documentRequestDTO,
            UriComponentsBuilder ucb) {

        // Map DTO to Entity
        Document newDocument = new Document(
                documentRequestDTO.originalFileName(),
                documentRequestDTO.fileType(),
                documentRequestDTO.sourceLanguage(),
                documentRequestDTO.targetLanguage()
        );

        Document savedDocument = documentService.save(newDocument);

        // Build Location URI for HATEOAS principle
        URI locationUri = ucb.path("/api/v1/documents/{id}")
                             .buildAndExpand(savedDocument.getId())
                             .toUri();

        return ResponseEntity.created(locationUri).body(savedDocument);
    }

    /**
     * GET /api/v1/documents/pending
     * Retrieves a list of documents that are in PENDING or PROCESSING status.
     * @return ResponseEntity with status 200 OK and a list of pending Documents.
     */
    @GetMapping("/pending")
    public ResponseEntity<List<Document>> getPendingDocuments() {
        List<Document> pendingDocuments = documentService.getPendingDocuments();
        return ResponseEntity.ok(pendingDocuments);
    }

    /**
     * GET /api/v1/documents/{id}/translations
     * Retrieves all translations associated with a specific document.
     * @param id The ID of the document.
     * @return ResponseEntity with status 200 OK and a list of Translations.
     */
    @GetMapping("/{id}/translations")
    public ResponseEntity<List<Translation>> getTranslationsByDocument(@PathVariable Long id) {
        List<Translation> translations = translationService.getTranslationsByDocument(id);
        return ResponseEntity.ok(translations);
    }

    /**
     * PATCH /api/v1/documents/{id}/status
     * Updates the status of a specific document.
     * @param id The ID of the document to update.
     * @param status The new status for the document (e.g., PENDING, PROCESSING, TRANSLATED, FAILED).
     * @return ResponseEntity with status 200 OK and the updated Document.
     */
    @PatchMapping("/{id}/status")
    public ResponseEntity<Document> updateDocumentStatus(
            @PathVariable Long id,
            @RequestParam DocumentStatus status) {
        Document updatedDocument = documentService.updateDocumentStatus(id, status);
        return ResponseEntity.ok(updatedDocument);
    }
}
