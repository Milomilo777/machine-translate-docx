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

            int positionalIndex = 0;

            // Manual space-separated argument parsing
            for (int i = 0; i < args.length; i++) {
                String arg = args[i];

                if ("--docxfile".equalsIgnoreCase(arg) && i + 1 < args.length) {
                    filePath = args[i + 1];
                    i++;
                } else if ("--destlang".equalsIgnoreCase(arg) && i + 1 < args.length) {
                    destLang = args[i + 1];
                    i++;
                } else if ("--target_lang".equalsIgnoreCase(arg) && i + 1 < args.length) {
                    destLang = args[i + 1];
                    i++;
                } else if ("--srclang".equalsIgnoreCase(arg) && i + 1 < args.length) {
                    sourceLang = args[i + 1];
                    i++;
                } else if ("--engine".equalsIgnoreCase(arg) && i + 1 < args.length) {
                    engine = parseEngineOrExit(args[i + 1]);
                    i++;
                } else if ("--split".equalsIgnoreCase(arg)
                        || "--showbrowser".equalsIgnoreCase(arg)
                        || "--exitonsuccess".equalsIgnoreCase(arg)
                        || "--viewdocx".equalsIgnoreCase(arg)
                        || "-l".equalsIgnoreCase(arg)) {
                    // Explicitly tolerate Python-only boolean flags
                } else if ("--xlsxreplacefile".equalsIgnoreCase(arg)) {
                    if (i + 1 < args.length && !args[i + 1].startsWith("-")) {
                        i++;
                    }
                } else if ("--destfont".equalsIgnoreCase(arg)) {
                    if (i + 1 < args.length && !args[i + 1].startsWith("-")) {
                        i++;
                    }
                } else if (!arg.startsWith("--") && !arg.startsWith("-")) {
                    // Add fallback for positional arguments if python passes them without flags
                    if (positionalIndex == 0 && filePath == null) {
                        filePath = arg;
                    } else if (positionalIndex == 1) {
                        destLang = arg;
                    } else if (positionalIndex == 2) {
                        engine = parseEngineOrExit(arg);
                    }
                    positionalIndex++;
                }
            }

            if (filePath == null) {
                System.out.println("Usage: java -jar app.jar --docxfile <path> --target_lang <code> --engine <engine>");
                exitApplication(1);
                return;
            }

            System.out.println("=========================================");
            System.out.println("   SMTV Translation Robot (Spring Boot)  ");
            System.out.println("=========================================");

            orchestrator.runTranslationJob(filePath, engine, sourceLang, destLang);

            System.out.println("[Success] Translation job completed.");

            exitApplication(0);
        } catch (Throwable t) {
            System.err.println("FATAL ERROR: " + t.getMessage());
            exitApplication(1);
        }
    }

    EngineType parseEngineOrExit(String engineArgValue) {
        try {
            EngineType parsedEngine = EngineType.fromString(engineArgValue);
            if (parsedEngine == EngineType.YANDEX ||
                    parsedEngine == EngineType.GOOGLE_API ||
                    parsedEngine == EngineType.DEEPL_API) {
                System.err.println("Engine " + parsedEngine.name() + " is disabled in this build.");
                exitApplication(2);
                return parsedEngine;
            }
            return parsedEngine;
        } catch (IllegalArgumentException e) {
            System.err.println("Unknown engine: " + engineArgValue);
            exitApplication(1);
            return EngineType.CHATGPT_API;
        }
    }

    void exitApplication(int code) {
        SpringApplication.exit(context, () -> code);
        System.exit(code);
    }
}
