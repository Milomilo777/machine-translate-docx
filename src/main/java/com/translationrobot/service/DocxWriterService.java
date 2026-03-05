package com.translationrobot.service;

import com.translationrobot.model.TranslationRow;

import java.util.List;

public interface DocxWriterService {
    String writeTranslatedDocx(String originalFilePath, List<TranslationRow> translatedRows, String destLangCode);
}
