package com.translationrobot.model;

import com.translationrobot.model.enums.TranslationEngineType;
import jakarta.persistence.*;
import java.util.Objects;
import java.util.UUID;

/**
 * Represents a single translation instance for a given text segment.
 */
@Entity
@Table(name = "translations")
public class Translation {

    @Id
    @Column(name = "id", updatable = false, nullable = false, columnDefinition = "BINARY(16)")
    private UUID id;

    @Lob // Used for mapping large String fields to appropriate LOB types (CLOB for String)
    @Column(name = "source_text", nullable = false)
    private String sourceText;

    @Lob // Used for mapping large String fields
    @Column(name = "translated_text", nullable = false)
    private String translatedText;

    @Enumerated(EnumType.STRING) // Stores the enum name as a String in the database
    @Column(name = "engine", nullable = false)
    private TranslationEngineType engine;

    @Column(name = "confidence_score") // Can be null if the engine doesn't provide it
    private Double confidenceScore;

    /**
     * Default constructor for JPA.
     */
    public Translation() {
        // JPA requires a no-arg constructor
    }

    /**
     * Constructor for creating a new Translation instance.
     * Generates a UUID for the ID.
     *
     * @param sourceText The original text segment.
     * @param translatedText The translated text segment.
     * @param engine The translation engine used.
     * @param confidenceScore The confidence score of the translation.
     */
    public Translation(String sourceText, String translatedText, TranslationEngineType engine, Double confidenceScore) {
        this.id = UUID.randomUUID(); // Application-level UUID generation
        this.sourceText = sourceText;
        this.translatedText = translatedText;
        this.engine = engine;
        this.confidenceScore = confidenceScore;
    }

    // --- Getters and Setters ---
    public UUID getId() {
        return id;
    }

    public String getSourceText() {
        return sourceText;
    }

    public void setSourceText(String sourceText) {
        this.sourceText = sourceText;
    }

    public String getTranslatedText() {
        return translatedText;
    }

    public void setTranslatedText(String translatedText) {
        this.translatedText = translatedText;
    }

    public TranslationEngineType getEngine() {
        return engine;
    }

    public void setEngine(TranslationEngineType engine) {
        this.engine = engine;
    }

    public Double getConfidenceScore() {
        return confidenceScore;
    }

    public void setConfidenceScore(Double confidenceScore) {
        this.confidenceScore = confidenceScore;
    }

    // --- Equals and HashCode ---
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Translation that = (Translation) o;
        return Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    // --- ToString ---
    @Override
    public String toString() {
        return "Translation{" +
               "id=" + id +
               ", sourceText='" + (sourceText.length() > 50 ? sourceText.substring(0, 47) + "..." : sourceText) + '\'' +
               ", translatedText='" + (translatedText.length() > 50 ? translatedText.substring(0, 47) + "..." : translatedText) + '\'' +
               ", engine=" + engine +
               ", confidenceScore=" + confidenceScore +
               '}';
    }
}
