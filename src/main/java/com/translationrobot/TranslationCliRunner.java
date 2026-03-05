package com.translationrobot;

import com.translationrobot.model.EngineType;
import com.translationrobot.service.TranslationOrchestrator;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class TranslationCliRunner implements CommandLineRunner {

    private final TranslationOrchestrator orchestrator;

    public TranslationCliRunner(TranslationOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @Override
    public void run(String... args) {
        if (args.length < 2) {
            System.out.println("Usage: java -jar app.jar <path_to_docx> <target_language_code> [engine_name]");
            return;
        }

        try {
            String filePath = args[0];
            String destLang = args[1];
            EngineType engine = EngineType.CHATGPT; // Default

            if (args.length >= 3) {
                engine = EngineType.valueOf(args[2].toUpperCase());
            }

            System.out.println("=========================================");
            System.out.println("   SMTV Translation Robot (Spring Boot)  ");
            System.out.println("=========================================");

            orchestrator.runTranslationJob(filePath, engine, "en", destLang);

            System.out.println("[Success] Translation job completed.");
        } catch (Exception e) {
            System.out.println("[Error] " + e.getMessage());
        }
    }
}
