package com.translationrobot.service;

import com.translationrobot.exception.EntityNotFoundException;
import com.translationrobot.model.Document;
import com.translationrobot.model.DocumentStatus;
import com.translationrobot.repository.DocumentRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;

@Service
@Transactional
public class DocumentServiceImpl implements DocumentService {

    private final DocumentRepository documentRepository;

    public DocumentServiceImpl(DocumentRepository documentRepository) {
        this.documentRepository = documentRepository;
    }

    @Override
    public Document save(Document document) {
        return documentRepository.save(document);
    }

    @Override
    @Transactional(readOnly = true)
    public List<Document> getPendingDocuments() {
        return documentRepository.findByStatusIn(Arrays.asList(DocumentStatus.PENDING, DocumentStatus.PROCESSING));
    }

    @Override
    public Document updateDocumentStatus(Long id, DocumentStatus status) {
        Document document = getDocumentById(id);
        document.setStatus(status);
        return documentRepository.save(document);
    }

    @Override
    @Transactional(readOnly = true)
    public Document getDocumentById(Long id) {
        return documentRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Document with ID " + id + " not found."));
    }
}
