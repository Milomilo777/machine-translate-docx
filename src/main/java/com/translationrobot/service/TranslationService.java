package com.translationrobot.service;

import com.translationrobot.model.Translation;
import java.util.List;

public interface TranslationService {
    List<Translation> getTranslationsByDocument(Long documentId);
}
