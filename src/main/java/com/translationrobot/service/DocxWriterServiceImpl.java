package com.translationrobot.service;

import com.translationrobot.model.TranslationRow;
import com.translationrobot.util.LanguageUtil;
import org.apache.poi.xwpf.usermodel.ParagraphAlignment;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFRun;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.apache.poi.xwpf.usermodel.XWPFTableCell;
import org.apache.poi.xwpf.usermodel.XWPFTableRow;
import org.springframework.stereotype.Service;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.List;

@Service
public class DocxWriterServiceImpl implements DocxWriterService {

    // @ArchitecturalNote: A robust baseline for safe DOCX manipulation.
    // In the future, this could be refactored to use Spring ApplicationEvents
    // for fully decoupled document saving.
    @Override
    public String writeTranslatedDocx(String originalFilePath, List<TranslationRow> translatedRows, String destLangCode) {
        String newFilePath = originalFilePath.replace(".docx", "_" + destLangCode.toUpperCase() + ".docx");

        try (FileInputStream fis = new FileInputStream(originalFilePath);
             XWPFDocument document = new XWPFDocument(fis)) {

            List<XWPFTable> tables = document.getTables();
            if (tables.isEmpty()) {
                throw new IllegalStateException("No tables found in the document.");
            }

            XWPFTable firstTable = tables.get(0);
            List<XWPFTableRow> tableRows = firstTable.getRows();

            for (TranslationRow row : translatedRows) {
                int rowIndex = row.getRowIndex();
                if (rowIndex >= tableRows.size()) {
                    continue; // Row index out of bounds, skip
                }

                XWPFTableRow tableRow = tableRows.get(rowIndex);
                XWPFTableCell cell = tableRow.getCell(2);
                if (cell == null) {
                    cell = tableRow.createCell();
                }

                // Safely remove all existing paragraphs
                while (!cell.getParagraphs().isEmpty()) {
                    cell.removeParagraph(0);
                }

                // Text Insertion
                XWPFParagraph newParagraph = cell.addParagraph();
                XWPFRun newRun = newParagraph.createRun();
                newRun.setText(row.getTargetText());

                // RTL Formatting
                if (LanguageUtil.isRtlLanguage(destLangCode)) {
                    newParagraph.setAlignment(ParagraphAlignment.RIGHT);
                    // POI CTR approach to set RTL on the run itself
                    if (newRun.getCTR().getRPr() == null) {
                        newRun.getCTR().addNewRPr();
                    }
                    if (newRun.getCTR().getRPr().getRtlList().isEmpty()) {
                        newRun.getCTR().getRPr().addNewRtl();
                    }
                } else {
                    newParagraph.setAlignment(ParagraphAlignment.LEFT);
                }
            }

            // Metadata
            document.getProperties().getCoreProperties().setDescription("Document translated by SMTV Robot (Spring Boot Migration)");

            // Save
            try (FileOutputStream fos = new FileOutputStream(newFilePath)) {
                document.write(fos);
            }

        } catch (IOException e) {
            throw new RuntimeException("Error writing translated DOCX file", e);
        }

        return newFilePath;
    }
}
