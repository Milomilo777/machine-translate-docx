package com.translationrobot.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocxCellData {
    private String text;
    private boolean isGrayed;
    private boolean isRed;
    private int numberOfLines;
}
