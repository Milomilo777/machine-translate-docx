package com.translationrobot;

import com.translationrobot.model.EngineType;
import com.translationrobot.service.TranslationOrchestrator;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ApplicationContext;
import org.springframework.stereotype.Component;

@Component
public class TranslationCliRunner implements CommandLineRunner {

    private final TranslationOrchestrator orchestrator;
    private final ApplicationContext context;

    public TranslationCliRunner(TranslationOrchestrator orchestrator, ApplicationContext context) {
        this.orchestrator = orchestrator;
        this.context = context;
    }

    @Override
    public void run(String... args) {
        try {
            if (args.length == 0) {
                // Might be started by Spring Boot Web or JavaFX, do nothing
                return;
            }

            String filePath = null;
            String destLang = "fa"; // default
            String sourceLang = "en"; // default
            EngineType engine = EngineType.CHATGPT_API; // default

            // Manual space-separated argument parsing
            for (int i = 0; i < args.length; i++) {
                if ("--docxfile".equalsIgnoreCase(args[i]) && i + 1 < args.length) {
                    filePath = args[i + 1];
                    i++;
                } else if ("--target_lang".equalsIgnoreCase(args[i]) && i + 1 < args.length) {
                    destLang = args[i + 1];
                    i++;
                } else if ("--engine".equalsIgnoreCase(args[i]) && i + 1 < args.length) {
                    String engineArgValue = args[i + 1];
                    try {
                        engine = EngineType.fromString(engineArgValue);
                    } catch (IllegalArgumentException e) {
                        System.err.println("Unknown engine: " + engineArgValue);
                        System.exit(1);
                    }
                    if (engine == EngineType.YANDEX ||
                        engine == EngineType.GOOGLE_API ||
                        engine == EngineType.DEEPL_API) {
                        System.err.println("Engine " + engine.name() + " is disabled in this build.");
                        System.exit(2);
                    }
                    i++;
                }
                // Add fallback for positional arguments if python passes them without flags
                else if (i == 0 && !args[i].startsWith("--")) {
                    filePath = args[i];
                } else if (i == 1 && !args[i].startsWith("--")) {
                    destLang = args[i];
                } else if (i == 2 && !args[i].startsWith("--")) {
                    String engineArgValue = args[i];
                    try {
                        engine = EngineType.fromString(engineArgValue);
                    } catch (IllegalArgumentException e) {
                        System.err.println("Unknown engine: " + engineArgValue);
                        System.exit(1);
                    }
                    if (engine == EngineType.YANDEX ||
                        engine == EngineType.GOOGLE_API ||
                        engine == EngineType.DEEPL_API) {
                        System.err.println("Engine " + engine.name() + " is disabled in this build.");
                        System.exit(2);
                    }
                }
            }

            if (filePath == null) {
                System.out.println("Usage: java -jar app.jar --docxfile <path> --target_lang <code> --engine <engine>");
                SpringApplication.exit(context, () -> 1);
                System.exit(1);
            }

            System.out.println("=========================================");
            System.out.println("   SMTV Translation Robot (Spring Boot)  ");
            System.out.println("=========================================");

            orchestrator.runTranslationJob(filePath, engine, sourceLang, destLang);

            System.out.println("[Success] Translation job completed.");

            SpringApplication.exit(context, () -> 0);
            System.exit(0);
        } catch (Throwable t) {
            System.err.println("FATAL ERROR: " + t.getMessage());
            SpringApplication.exit(context, () -> 1);
            System.exit(1);
        }
    }
}
