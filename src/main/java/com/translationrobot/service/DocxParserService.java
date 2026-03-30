package com.translationrobot.service;

import com.translationrobot.model.TranslationRow;
import java.util.List;

public interface DocxParserService {
    List<TranslationRow> parseDocument(String filePath);
}
