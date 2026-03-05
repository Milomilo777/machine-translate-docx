package com.translationrobot.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TranslationRow {
    private int rowIndex;
    private DocxCellData sourceData;
    private String targetText;
}
