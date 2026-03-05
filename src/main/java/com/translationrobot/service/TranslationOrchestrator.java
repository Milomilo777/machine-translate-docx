package com.translationrobot.service;

import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.engine.TranslationEngineFactory;
import com.translationrobot.exception.TranslationMismatchException;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationLog;
import com.translationrobot.model.TranslationResponse;
import com.translationrobot.model.TranslationRow;
import com.translationrobot.repository.TranslationLogRepository;
import com.translationrobot.util.LanguageUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
public class TranslationOrchestrator {

    private final DocxParserService docxParserService;
    private final TranslationEngineFactory translationEngineFactory;
    private final TranslationLogRepository translationLogRepository;
    private final DocxWriterService docxWriterService;

    public TranslationOrchestrator(DocxParserService docxParserService,
                                   TranslationEngineFactory translationEngineFactory,
                                   TranslationLogRepository translationLogRepository,
                                   DocxWriterService docxWriterService) {
        this.docxParserService = docxParserService;
        this.translationEngineFactory = translationEngineFactory;
        this.translationLogRepository = translationLogRepository;
        this.docxWriterService = docxWriterService;
    }

    public void runTranslationJob(String filePath, EngineType engineType, String srcLang, String destLang) {
        // a) Call DocxParserService to get List<TranslationRow>
        List<TranslationRow> rows = docxParserService.parseDocument(filePath);

        if (rows.isEmpty()) {
            return;
        }

        // 1. Separate 'TranslationRow' objects into two streams: toTranslate and toSkip
        List<TranslationRow> toTranslate = rows.stream()
                .filter(row -> {
                    String text = row.getSourceData().getText();
                    return text != null && !text.trim().isEmpty()
                            && !row.getSourceData().isRed()
                            && !row.getSourceData().isGrayed()
                            && !LanguageUtil.isIgnoredText(text);
                })
                .collect(Collectors.toList());

        List<TranslationRow> toSkip = rows.stream()
                .filter(row -> {
                    String text = row.getSourceData().getText();
                    return text == null || text.trim().isEmpty()
                            || row.getSourceData().isRed()
                            || row.getSourceData().isGrayed()
                            || LanguageUtil.isIgnoredText(text);
                })
                .collect(Collectors.toList());

        // 2. For 'toSkip' rows: Immediately set 'targetText' equal to 'sourceData.text()'
        for (TranslationRow row : toSkip) {
            row.setTargetText(row.getSourceData().getText());
        }

        log.info("Rows to translate: {}, Rows to skip: {}", toTranslate.size(), toSkip.size());

        if (!toTranslate.isEmpty()) {
            // 3. For 'toTranslate' rows: Combine them into a single string
            String combinedText = toTranslate.stream()
                    .map(row -> row.getSourceData().getText())
                    .collect(Collectors.joining("\n"));

            // c) Call engine.translate() with retry logic
            // @ModernizationProposal: Consider using Spring Retry (@Retryable) or Resilience4j for this logic.
            TranslationEngine engine = translationEngineFactory.getEngine(engineType);
            TranslationResponse response = null;
            int maxRetries = 3;
            for (int attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    response = engine.translate(srcLang, destLang, combinedText);
                    break;
                } catch (Exception e) {
                    log.warn("Translation attempt {} failed: {}", attempt, e.getMessage());
                    if (attempt == maxRetries) {
                        throw new RuntimeException("Translation failed after " + maxRetries + " attempts", e);
                    }
                    try {
                        Thread.sleep(2000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Retry interrupted", ie);
                    }
                }
            }

            // d) Save the execution metrics
            TranslationLog tLog = TranslationLog.builder()
                    .documentName(filePath)
                    .engineName(engineType.name())
                    .inputTokens(response.inputTokens())
                    .outputTokens(response.outputTokens())
                    .totalCostUsd(response.totalCostUsd())
                    .executionTimeSec(response.executionTimeSec())
                    .timestamp(LocalDateTime.now())
                    .build();
            translationLogRepository.save(tLog);

            // e) Map the returned lines back to the correct rows
            String[] translatedLines = response.translatedText().split("\n");

            if (translatedLines.length != toTranslate.size()) {
                throw new TranslationMismatchException("Number of returned translated lines (" + translatedLines.length +
                        ") does not equal the number of input lines (" + toTranslate.size() + ")");
            }

            for (int i = 0; i < toTranslate.size(); i++) {
                toTranslate.get(i).setTargetText(translatedLines[i]);
            }
        }

        // f) Write translated DOCX
        String newFilePath = docxWriterService.writeTranslatedDocx(filePath, rows, destLang);
        log.info("Translation complete. Document saved to: {}", newFilePath);
    }
}
