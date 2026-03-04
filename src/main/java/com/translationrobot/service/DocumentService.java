package com.translationrobot.service;

import com.translationrobot.model.Document;
import com.translationrobot.model.DocumentStatus;
import java.util.List;

public interface DocumentService {
    Document save(Document document);
    List<Document> getPendingDocuments();
    Document updateDocumentStatus(Long id, DocumentStatus status);
    Document getDocumentById(Long id); // Added for internal use in update status
}
