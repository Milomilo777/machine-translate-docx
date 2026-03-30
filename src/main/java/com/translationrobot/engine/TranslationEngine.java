package com.translationrobot.engine;

import com.translationrobot.model.EngineType;

public interface TranslationEngine {
    boolean supports(EngineType type);
    com.translationrobot.model.TranslationResponse translate(String sourceLang, String targetLang, String text);
}
