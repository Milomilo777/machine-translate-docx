package com.translationrobot.service.impl;

import com.translationrobot.exception.EntityNotFoundException;
import com.translationrobot.model.Document;
import com.translationrobot.model.enums.DocumentStatus;
import com.translationrobot.repository.DocumentRepository;
import com.translationrobot.service.DocumentService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * Implementation of {@link DocumentService} providing business logic for document management.
 */
@Service
@Transactional // Ensures all public methods are transactional by default
public class DocumentServiceImpl implements DocumentService {

    private final DocumentRepository documentRepository;

    /**
     * Constructor for dependency injection.
     * Repositories are injected using Constructor Injection.
     *
     * @param documentRepository The repository for Document entities.
     */
    public DocumentServiceImpl(DocumentRepository documentRepository) {
        this.documentRepository = documentRepository;
    }

    @Override
    public Document saveDocument(Document document) {
        // If it's a new document and status isn't explicitly set, default to UPLOADED
        if (document.getId() == null && document.getStatus() == null) {
            document.setStatus(DocumentStatus.UPLOADED);
        }
        return documentRepository.save(document);
    }

    @Override
    @Transactional(readOnly = true) // Optimize read operations
    public Document getDocumentById(UUID id) {
        return documentRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Document", id));
    }

    @Override
    public Document updateDocumentStatus(UUID id, DocumentStatus newStatus) {
        // Validation: Check for entity existence before updates
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Document", id));

        document.setStatus(newStatus);
        document.setLastModifiedDate(LocalDateTime.now()); // Update last modified timestamp
        return documentRepository.save(document);
    }

    @Override
    @Transactional(readOnly = true) // Optimize read operations
    public List<Document> getPendingDocuments() {
        // Specific Logic: query DocumentRepository for status 'UPLOADED'.
        return documentRepository.findByStatus(DocumentStatus.UPLOADED);
    }
}
