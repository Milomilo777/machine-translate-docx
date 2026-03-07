package com.translationrobot.service;

import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.engine.TranslationEngineFactory;
import com.translationrobot.model.DocxCellData;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import com.translationrobot.model.TranslationRow;
import com.translationrobot.repository.TranslationLogRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

class TranslationOrchestratorMismatchTest {

    private TranslationOrchestrator orchestrator;
    private DocxParserService docxParserService;
    private TranslationEngineFactory translationEngineFactory;
    private TranslationLogRepository translationLogRepository;
    private DocxWriterService docxWriterService;
    private TranslationEngine translationEngine;

    @BeforeEach
    void setUp() {
        docxParserService = mock(DocxParserService.class);
        translationEngineFactory = mock(TranslationEngineFactory.class);
        translationLogRepository = mock(TranslationLogRepository.class);
        docxWriterService = mock(DocxWriterService.class);
        translationEngine = mock(TranslationEngine.class);

        when(translationEngineFactory.getEngine(any(EngineType.class))).thenReturn(translationEngine);

        orchestrator = new TranslationOrchestrator(
                docxParserService,
                translationEngineFactory,
                translationLogRepository,
                docxWriterService
        );
    }

    @Test
    void testGracefulDegradationOnLineMismatch() {
        // Arrange
        String filePath = "test.docx";
        EngineType engineType = EngineType.CHATGPT;
        String srcLang = "en";
        String destLang = "fa";

        List<TranslationRow> inputRows = new ArrayList<>();
        inputRows.add(TranslationRow.builder().rowIndex(0).sourceData(DocxCellData.builder().text("Line 1").build()).build());
        inputRows.add(TranslationRow.builder().rowIndex(1).sourceData(DocxCellData.builder().text("Line 2").build()).build());
        inputRows.add(TranslationRow.builder().rowIndex(2).sourceData(DocxCellData.builder().text("Line 3").build()).build());

        when(docxParserService.parseDocument(filePath)).thenReturn(inputRows);

        // Mock LLM returning only 2 lines instead of 3
        TranslationResponse mockResponse = new TranslationResponse("Translated Line 1\nTranslated Line 2", 10, 10, 0.01, 1.0);
        when(translationEngine.translate(eq(srcLang), eq(destLang), anyString())).thenReturn(mockResponse);

        // Act
        orchestrator.runTranslationJob(filePath, engineType, srcLang, destLang);

        // Assert
        ArgumentCaptor<List<TranslationRow>> rowsCaptor = ArgumentCaptor.forClass((Class) List.class);
        verify(docxWriterService).writeTranslatedDocx(eq(filePath), rowsCaptor.capture(), eq(destLang));

        List<TranslationRow> processedRows = rowsCaptor.getValue();

        assertTrue(processedRows.get(0).getTargetText().contains("[SMTV_REVIEW_NEEDED: LINE MISMATCH]"),
                "First row should contain the review needed flag");
        assertTrue(processedRows.get(1).getTargetText().contains("[LLM_SKIPPED]"),
                "Second row should contain the skipped flag");
        assertTrue(processedRows.get(2).getTargetText().contains("[LLM_SKIPPED]"),
                "Third row should contain the skipped flag");
    }
}
