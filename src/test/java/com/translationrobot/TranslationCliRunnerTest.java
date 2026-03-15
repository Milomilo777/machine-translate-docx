package com.translationrobot;

import com.translationrobot.model.EngineType;
import com.translationrobot.service.TranslationOrchestrator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class TranslationCliRunnerTest {

    private TranslationOrchestrator orchestrator;
    private ApplicationContext context;
    private TestableTranslationCliRunner runner;

    @BeforeEach
    void setUp() {
        orchestrator = mock(TranslationOrchestrator.class);
        context = mock(ApplicationContext.class);
        runner = new TestableTranslationCliRunner(orchestrator, context);
    }

    @Test
    void pythonGuiStyleArgs_AreParsedCorrectly() {
        doNothing().when(orchestrator).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());

        runner.run(
                "--srclang", "en",
                "--destlang", "fa",
                "--engine", "chatgpt-api",
                "--docxfile", "C:/tmp/in.docx"
        );

        verify(orchestrator).runTranslationJob("C:/tmp/in.docx", EngineType.CHATGPT_API, "en", "fa");
        assertEquals(0, runner.exitCode);
    }

    @Test
    void legacyChatgpt_MapsToWeb() {
        doNothing().when(orchestrator).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());

        runner.run(
                "--srclang", "en",
                "--destlang", "fa",
                "--engine", "chatgpt",
                "--docxfile", "C:/tmp/in.docx"
        );

        verify(orchestrator).runTranslationJob("C:/tmp/in.docx", EngineType.CHATGPT_WEB, "en", "fa");
        assertEquals(0, runner.exitCode);
    }

    @Test
    void pythonOnlyFlags_AreIgnoredSafely() {
        doNothing().when(orchestrator).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());

        runner.run(
                "--split",
                "--showbrowser",
                "--xlsxreplacefile", "C:/tmp/memory.xlsx",
                "--destfont", "Arial",
                "--exitonsuccess",
                "-l",
                "--srclang", "en",
                "--destlang", "fa",
                "--engine", "deepl",
                "--docxfile", "C:/tmp/in.docx"
        );

        verify(orchestrator).runTranslationJob("C:/tmp/in.docx", EngineType.DEEPL, "en", "fa");
        assertEquals(0, runner.exitCode);
    }

    @Test
    void missingFilePath_DoesNotCallOrchestrator() {
        runner.run(
                "--srclang", "en",
                "--destlang", "fa",
                "--engine", "chatgpt-api"
        );

        verify(orchestrator, never()).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());
        assertEquals(1, runner.exitCode);
    }

    @Test
    void missingOptionalValueFlags_DoNotStealFollowingArgs() {
        doNothing().when(orchestrator).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());

        runner.run(
                "--xlsxreplacefile",
                "--destfont",
                "--srclang", "en",
                "--destlang", "fa",
                "--engine", "deepl",
                "--docxfile", "C:/tmp/in.docx"
        );

        verify(orchestrator).runTranslationJob("C:/tmp/in.docx", EngineType.DEEPL, "en", "fa");
        assertEquals(0, runner.exitCode);
    }

    static class TestableTranslationCliRunner extends TranslationCliRunner {

        Integer exitCode;

        TestableTranslationCliRunner(TranslationOrchestrator orchestrator, ApplicationContext context) {
            super(orchestrator, context);
        }

        @Override
        void exitApplication(int code) {
            this.exitCode = code;
        }
    }
}
