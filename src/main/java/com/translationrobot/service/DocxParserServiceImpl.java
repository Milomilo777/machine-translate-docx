package com.translationrobot.service;

import com.translationrobot.model.DocxCellData;
import com.translationrobot.model.TranslationRow;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFRun;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.apache.poi.xwpf.usermodel.XWPFTableCell;
import org.apache.poi.xwpf.usermodel.XWPFTableRow;
import org.springframework.stereotype.Service;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class DocxParserServiceImpl implements DocxParserService {

    private static final Pattern PAUSE_PATTERN = Pattern.compile("(?i)<pause>");
    private static final Pattern ENTER_PATTERN = Pattern.compile("(?i)<enter>");

    @Override
    public List<TranslationRow> parseDocument(String filePath) {
        List<TranslationRow> rows = new ArrayList<>();

        try (FileInputStream fis = new FileInputStream(filePath);
             XWPFDocument document = new XWPFDocument(fis)) {

            List<XWPFTable> tables = document.getTables();
            if (tables.isEmpty()) {
                return rows;
            }

            XWPFTable firstTable = tables.get(0);
            List<XWPFTableRow> tableRows = firstTable.getRows();

            for (int rowIndex = 0; rowIndex < tableRows.size(); rowIndex++) {
                XWPFTableRow row = tableRows.get(rowIndex);
                List<XWPFTableCell> cells = row.getTableCells();

                // Assuming column index 1 is the 2nd column (source text)
                if (cells.size() > 1) {
                    XWPFTableCell sourceCell = cells.get(1);
                    DocxCellData cellData = extractCellData(sourceCell);

                    TranslationRow translationRow = TranslationRow.builder()
                            .rowIndex(rowIndex)
                            .sourceData(cellData)
                            .targetText(null) // Target text will be filled in Phase 2
                            .build();

                    rows.add(translationRow);
                }
            }

        } catch (IOException e) {
            throw new RuntimeException("Error reading DOCX file: " + filePath, e);
        }

        return rows;
    }

    private DocxCellData extractCellData(XWPFTableCell cell) {
        StringBuilder cellTextBuilder = new StringBuilder();
        boolean isGrayed = false;
        boolean isRed = false;
        int numberOfLines = 1;

        for (XWPFParagraph paragraph : cell.getParagraphs()) {
            String pText = paragraph.getText();

            // Count pause and enter tags for numberOfLines
            Matcher pauseMatcher = PAUSE_PATTERN.matcher(pText);
            while (pauseMatcher.find()) {
                numberOfLines++;
            }
            Matcher enterMatcher = ENTER_PATTERN.matcher(pText);
            while (enterMatcher.find()) {
                numberOfLines++;
            }

            for (XWPFRun run : paragraph.getRuns()) {
                String runText = run.text();

                // Red detection based on Python script
                if ("FF0000".equals(run.getColor())) {
                    isRed = true;
                }

                // Gray/Shaded detection (Python script checks highlight color)
                if (run.getTextHighlightColor() != null) {
                    String highlightColor = run.getTextHighlightColor().toString();
                    if ("darkGray".equalsIgnoreCase(highlightColor) ||
                        "lightGray".equalsIgnoreCase(highlightColor) ||
                        "magenta".equalsIgnoreCase(highlightColor) ||
                        "red".equalsIgnoreCase(highlightColor)) {
                        isGrayed = true;
                    }
                }
                if (run.isStrikeThrough() || run.isDoubleStrikeThrough()) {
                    isGrayed = true;
                }

                if (runText != null && !runText.isEmpty()) {
                    cellTextBuilder.append(runText);
                }
            }
        }

        String rawText = cellTextBuilder.toString();

        // Clean text like the Python regexes
        String cleanedText = PAUSE_PATTERN.matcher(rawText).replaceAll(" ");
        cleanedText = ENTER_PATTERN.matcher(cleanedText).replaceAll(" ");
        cleanedText = cleanedText.replaceAll("[\\r\\n\\u2028\\u2029]+", " ");
        cleanedText = cleanedText.replaceAll(" +", " ").trim();

        return DocxCellData.builder()
                .text(cleanedText)
                .isGrayed(isGrayed)
                .isRed(isRed)
                .numberOfLines(numberOfLines)
                .build();
    }
}
