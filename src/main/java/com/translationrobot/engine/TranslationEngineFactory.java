package com.translationrobot.engine;

import com.translationrobot.model.EngineType;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class TranslationEngineFactory {

    private final List<TranslationEngine> engines;

    public TranslationEngineFactory(List<TranslationEngine> engines) {
        this.engines = engines;
    }

    public TranslationEngine getEngine(EngineType type) {
        if (type == EngineType.YANDEX ||
                type == EngineType.GOOGLE_API ||
                type == EngineType.DEEPL_API) {
            throw new IllegalArgumentException("Engine " + type.name() + " is disabled in this build.");
        }

        return engines.stream()
                .filter(engine -> engine.supports(type))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("No translation engine found for type: " + type));
    }
}
