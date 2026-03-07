package com.translationrobot.service;

import com.translationrobot.model.TranslationRow;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.FileOutputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

class DocxEdgeCaseTest {

    @Test
    void parseEmptyDocument_ShouldReturnEmptyList() throws Exception {
        File tempFile = File.createTempFile("empty", ".docx");
        try (XWPFDocument doc = new XWPFDocument();
             FileOutputStream out = new FileOutputStream(tempFile)) {
            doc.write(out);
        }

        DocxParserService parserService = new DocxParserServiceImpl();
        List<TranslationRow> result = parserService.parseDocument(tempFile.getAbsolutePath());

        assertTrue(result.isEmpty(), "Empty document should return an empty list");

        tempFile.delete();
    }
}
