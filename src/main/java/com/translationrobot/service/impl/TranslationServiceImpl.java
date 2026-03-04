package com.translationrobot.service.impl;

import com.translationrobot.exception.EntityNotFoundException;
import com.translationrobot.model.Document;
import com.translationrobot.model.Translation;
import com.translationrobot.model.enums.TranslationEngineType;
import com.translationrobot.repository.DocumentRepository;
import com.translationrobot.repository.TranslationRepository;
import com.translationrobot.service.TranslationService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

/**
 * Implementation of {@link TranslationService} providing business logic for translation management.
 */
@Service
@Transactional // Ensures all public methods are transactional by default
public class TranslationServiceImpl implements TranslationService {

    private final TranslationRepository translationRepository;
    private final DocumentRepository documentRepository; // Needed to fetch the Document entity

    /**
     * Constructor for dependency injection.
     * Repositories are injected using Constructor Injection.
     *
     * @param translationRepository The repository for Translation entities.
     * @param documentRepository The repository for Document entities.
     */
    public TranslationServiceImpl(TranslationRepository translationRepository, DocumentRepository documentRepository) {
        this.translationRepository = translationRepository;
        this.documentRepository = documentRepository;
    }

    @Override
    public void saveTranslation(UUID documentId, String sourceText, String translatedText, TranslationEngineType engine) {
        // Fetch the Document entity to associate the translation with it.
        Document document = documentRepository.findById(documentId)
                .orElseThrow(() -> new EntityNotFoundException("Document", documentId));

        Translation translation = new Translation();
        translation.setDocument(document);
        translation.setSourceText(sourceText);
        translation.setTranslatedText(translatedText);
        translation.setEngineType(engine);
        // The 'translationDate' will be automatically set by @PrePersist in the Translation model.

        translationRepository.save(translation);
    }

    @Override
    @Transactional(readOnly = true) // Optimize read operations
    public List<Translation> getTranslationsByDocument(UUID documentId) {
        // Retrieves translations. If no translations exist for the document, an empty list is returned.
        // It's generally fine to return an empty list if the parent document exists but has no children.
        // If you need to explicitly check for document existence first, uncomment the lines below:
        // documentRepository.findById(documentId)
        //         .orElseThrow(() -> new EntityNotFoundException("Document", documentId));
        return translationRepository.findByDocumentId(documentId);
    }
}
