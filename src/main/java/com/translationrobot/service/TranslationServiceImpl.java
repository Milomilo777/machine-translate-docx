package com.translationrobot.service;

import com.translationrobot.client.TranslationClient;
import com.translationrobot.exception.TranslationApiException;
import com.translationrobot.model.Document;
import com.translationrobot.model.DocumentStatus;
import com.translationrobot.model.Translation;
import com.translationrobot.repository.DocumentRepository;
import com.translationrobot.repository.TranslationRepository;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class TranslationServiceImpl implements TranslationService {

    private final DocumentRepository documentRepository;
    private final TranslationRepository translationRepository;
    private final TranslationClient googleTranslationClient; // Injected specific client

    public TranslationServiceImpl(DocumentRepository documentRepository,
                                  TranslationRepository translationRepository,
                                  TranslationClient googleTranslationClient) {
        this.documentRepository = documentRepository;
        this.translationRepository = translationRepository;
        this.googleTranslationClient = googleTranslationClient;
    }

    @Async // Task 2: Asynchronous Processing Logic
    @Override
    @Transactional // Engineering Constraint: Data Consistency - Ensures all DB ops within this method are atomic
    public void processDocument(UUID documentId) {
        System.out.println("Starting async processing for document: " + documentId + " on thread: " + Thread.currentThread().getName());

        // Step A: Fetch document, update status to PROCESSING.
        Optional<Document> documentOptional = documentRepository.findById(documentId);
        if (documentOptional.isEmpty()) {
            System.err.println("Document with ID " + documentId + " not found. Aborting translation.");
            return;
        }

        Document document = documentOptional.get();
        document.setStatus(DocumentStatus.PROCESSING);
        documentRepository.save(document); // Persist status change immediately
        System.out.println("Document " + documentId + " status updated to PROCESSING.");

        try {
            // Step B: Iterate through segments (logic for split can be simple for now).
            // Simple split by sentence (period, question mark, exclamation mark)
            String[] segments = document.getContent().split("(?<=[.!?])\\s*");
            List<String> segmentList = Arrays.asList(segments);

            for (String originalSegment : segmentList) {
                if (originalSegment.trim().isEmpty()) continue; // Skip empty segments

                String translatedSegment;
                try {
                    // Step C: Call TranslationClient for each segment.
                    // Reliability: Add simple try-catch logic to handle API timeouts/errors.
                    translatedSegment = googleTranslationClient.translate(
                        originalSegment.trim(),
                        document.getSourceLanguage(),
                        document.getTargetLanguage()
                    );
                    System.out.println("Segment translated successfully: '" + originalSegment + "'");

                } catch (TranslationApiException e) {
                    System.err.println("Failed to translate segment for document " + documentId + ": '" + originalSegment + "'. Error: " + e.getMessage());
                    // Reliability: If an error occurs, set Document status to FAILED.
                    document.setStatus(DocumentStatus.FAILED);
                    documentRepository.save(document);
                    System.out.println("Document " + documentId + " status updated to FAILED due to translation error. Aborting further segments.");
                    return; // Stop processing further segments for this document
                }

                // Step D: Save each 'Translation' entity linked to the 'Document'.
                Translation translation = new Translation();
                translation.setDocument(document);
                translation.setOriginalSegment(originalSegment.trim());
                translation.setTranslatedSegment(translatedSegment);
                translation.setSourceLanguage(document.getSourceLanguage());
                translation.setTargetLanguage(document.getTargetLanguage());
                translation.setEngineType(googleTranslationClient.getEngineType()); // Reliability: Tracking engineType
                translationRepository.save(translation);
            }

            // Step E: Update Document status to TRANSLATED upon completion.
            document.setStatus(DocumentStatus.TRANSLATED);
            documentRepository.save(document);
            System.out.println("Document " + documentId + " successfully translated and status updated to TRANSLATED.");

        } catch (Exception e) {
            // Catch any other unexpected errors that might occur during the overall process
            System.err.println("An unexpected error occurred during processing document " + documentId + ": " + e.getMessage());
            document.setStatus(DocumentStatus.FAILED);
            documentRepository.save(document);
            System.out.println("Document " + documentId + " status updated to FAILED due to unexpected internal error.");
        }
    }
}
