package com.translationrobot.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * DTO for creating a new document request.
 * Decouples API contract from internal JPA entities.
 * Uses Java 17 Record for conciseness and immutability.
 */
public record DocumentRequestDTO(
        @NotBlank(message = "Original file name cannot be blank.")
        @Size(min = 1, max = 255, message = "Original file name must be between 1 and 255 characters.")
        String originalFileName,

        @NotBlank(message = "File type cannot be blank.")
        @Pattern(regexp = "^(docx|pdf|txt)$", message = "File type must be 'docx', 'pdf', or 'txt'.")
        String fileType,

        @NotBlank(message = "Source language cannot be blank.")
        String sourceLanguage,

        @NotBlank(message = "Target language cannot be blank.")
        String targetLanguage
) {
}
