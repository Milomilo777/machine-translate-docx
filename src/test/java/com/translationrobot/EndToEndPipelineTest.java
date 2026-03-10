package com.translationrobot;

import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.engine.TranslationEngineFactory;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationLog;
import com.translationrobot.model.TranslationResponse;
import com.translationrobot.repository.TranslationLogRepository;
import com.translationrobot.service.TranslationOrchestrator;
import org.apache.poi.xwpf.usermodel.*;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@SpringBootTest(properties = {
        "spring.main.web-application-type=none",
        "spring.datasource.url=jdbc:h2:mem:testdb",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=password",
        "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect",
        "spring.jpa.hibernate.ddl-auto=update",
        "openai.api.key=dummy"
})
public class EndToEndPipelineTest {

    @MockBean
    TranslationCliRunner cliRunner;

    @MockBean
    TranslationEngineFactory factory;


    @Autowired
    TranslationOrchestrator orchestrator;

    @Autowired
    TranslationLogRepository logRepo;

    private String tempFilePath;
    private String outFilePath;

    @BeforeEach
    void setUp() throws Exception {
        logRepo.deleteAll();

        // 1. Setup File
        File tempFile = new File(System.getProperty("java.io.tmpdir"), "e2e_test.docx");
        tempFilePath = tempFile.getAbsolutePath();
        outFilePath = tempFilePath.replace(".docx", "_FA.docx");

        try (XWPFDocument doc = new XWPFDocument()) {
            XWPFTable table = doc.createTable(3, 3);

            // Row 1: Normal
            table.getRow(0).getCell(1).setText("Hello World");

            // Row 2: Red text (bypassed)
            XWPFParagraph p2 = table.getRow(1).getCell(1).addParagraph();
            XWPFRun r2 = p2.createRun();
            r2.setText("Code();");
            r2.setColor("FF0000");

            // Row 3: Punctuation (bypassed)
            table.getRow(2).getCell(1).setText("-");

            try (FileOutputStream fos = new FileOutputStream(tempFile)) {
                doc.write(fos);
            }
        }
    }

    @Test
    void testFullPipeline_FromDocxToDatabase() throws Exception {
        // 2. Setup Mock API
        TranslationEngine mockEngine = org.mockito.Mockito.mock(TranslationEngine.class);
        when(factory.getEngine(any(EngineType.class))).thenReturn(mockEngine);
        when(mockEngine.supports(any(EngineType.class))).thenReturn(true);
        when(mockEngine.translate(anyString(), anyString(), anyString()))
                .thenReturn(new TranslationResponse("سلام دنیا", 1000, 500, 0.00625, 1.0));

        // 3. Execute
        orchestrator.runTranslationJob(tempFilePath, EngineType.CHATGPT_API, "en", "fa");

        // 4. Assert File I/O
        File outFile = new File(outFilePath);
        assertTrue(outFile.exists(), "Output file was not created");

        try (FileInputStream fis = new FileInputStream(outFile);
             XWPFDocument outDoc = new XWPFDocument(fis)) {
            XWPFTable table = outDoc.getTables().get(0);

            String row1Text = table.getRow(0).getCell(2).getText();
            String row2Text = table.getRow(1).getCell(2).getText();
            String row3Text = table.getRow(2).getCell(2).getText();

            assertTrue(row1Text.contains("سلام دنیا"), "Row 1 should contain translated text");
            assertTrue(row2Text.contains("Code();"), "Row 2 should contain bypassed red text");
            assertTrue(row3Text.contains("-"), "Row 3 should contain bypassed punctuation");
        }

        // 5. Assert Database Math
        List<TranslationLog> logs = logRepo.findAll();
        assertEquals(1, logs.size(), "Should have exactly one log entry");
        assertEquals(0.00625, logs.get(0).getCostUsd(), 0.00001, "Cost USD should match exactly");
        assertEquals("CHATGPT", logs.get(0).getModelName());
    }

    @AfterEach
    void tearDown() {
        if (tempFilePath != null) {
            new File(tempFilePath).delete();
        }
        if (outFilePath != null) {
            new File(outFilePath).delete();
        }
    }
}
