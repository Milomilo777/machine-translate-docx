package com.translationrobot.controller;

import com.translationrobot.model.EngineType;
import com.translationrobot.service.TranslationOrchestrator;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.doNothing;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(WebController.class)
class WebControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TranslationOrchestrator orchestrator;

    @Test
    void uploadFileSuccess_ShouldReturn200AndFile() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "test.docx",
                MediaType.APPLICATION_OCTET_STREAM_VALUE,
                "dummy content".getBytes()
        );

        doNothing().when(orchestrator).runTranslationJob(anyString(), any(EngineType.class), anyString(), anyString());

        // In MockMvc, a multipart request needs the file name to match the controller's @RequestParam("file").
        // We already named it "file" in the MockMultipartFile constructor above.

        mockMvc.perform(multipart("/translate")
                        .file(file)
                        .param("sourceLang", "en")
                        .param("targetLang", "fa")
                        .param("engine", "CHATGPT")
                        .param("split", "false"))
                .andExpect(status().isOk())
                .andExpect(header().exists("Content-Disposition"));
    }

    @Test
    void uploadMissingFile_ShouldReturn400() throws Exception {
        mockMvc.perform(multipart("/translate")
                        .param("sourceLang", "en")
                        .param("targetLang", "fa")
                        .param("engine", "CHATGPT"))
                .andExpect(status().isBadRequest());
    }
}
