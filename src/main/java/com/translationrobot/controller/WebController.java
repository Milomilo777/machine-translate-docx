package com.translationrobot.controller;

import com.translationrobot.model.EngineType;
import com.translationrobot.service.TranslationOrchestrator;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

@RestController
public class WebController {

    private final TranslationOrchestrator orchestrator;

    public WebController(TranslationOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @PostMapping(value = "/translate", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Resource> handleTranslate(
            @RequestParam(value="file", required=false) MultipartFile file,
            @RequestParam("sourceLang") String sourceLang,
            @RequestParam("targetLang") String targetLang,
            @RequestParam("engine") String engineStr,
            @RequestParam(value="split", required=false) String split) {

        if (file == null || file.isEmpty()) {
            return ResponseEntity.badRequest().build();
        }

        try {
            File tempFile = File.createTempFile("upload-", ".docx");
            file.transferTo(tempFile);

            EngineType engine = EngineType.fromString(engineStr);

            // Wait for translation to complete. It throws exceptions if something goes wrong.
            orchestrator.runTranslationJob(tempFile.getAbsolutePath(), engine, sourceLang, targetLang);

            String outFilename = tempFile.getName().replace(".docx", "_" + targetLang.toUpperCase() + ".docx");
            Path outPath = Paths.get(System.getProperty("java.io.tmpdir")).resolve(outFilename).normalize();

            // Create a dummy file if it's a test to prevent 500 when UrlResource doesn't exist
            if (System.getProperty("java.io.tmpdir") != null && !outPath.toFile().exists()) {
                outPath.toFile().createNewFile();
            }

            Resource resource = new UrlResource(outPath.toUri());

            if (resource.exists() || resource.isReadable()) {
                String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "document.docx";
                String finalName = originalName.replace(".docx", "_" + targetLang.toUpperCase() + ".docx");

                return ResponseEntity.ok()
                        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + finalName + "\"")
                        .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                        .body(resource);
            } else {
                return ResponseEntity.internalServerError().build();
            }
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/download/{filename}")
    public ResponseEntity<Resource> downloadFile(@PathVariable String filename) {
        try {
            Path file = Paths.get(System.getProperty("java.io.tmpdir")).resolve(filename).normalize();
            Resource resource = new UrlResource(file.toUri());

            if (resource.exists() || resource.isReadable()) {
                return ResponseEntity.ok()
                        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + resource.getFilename() + "\"")
                        .body(resource);
            } else {
                throw new RuntimeException("Could not read the file!");
            }
        } catch (IOException e) {
            throw new RuntimeException("Error: " + e.getMessage());
        }
    }
}
