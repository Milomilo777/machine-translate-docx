package com.translationrobot.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "translations")
public class Translation {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID) // Engineering Constraint: UUIDs
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "document_id", nullable = false)
    private Document document;

    @Column(columnDefinition = "TEXT")
    private String originalSegment;

    @Column(columnDefinition = "TEXT")
    private String translatedSegment;

    private String engineType; // Reliability: Tracking engineType (e.g., GOOGLE)
    private String sourceLanguage;
    private String targetLanguage;
    private LocalDateTime translatedAt;

    public Translation() {
        this.translatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public Document getDocument() { return document; }
    public void setDocument(Document document) { this.document = document; }
    public String getOriginalSegment() { return originalSegment; }
    public void setOriginalSegment(String originalSegment) { this.originalSegment = originalSegment; }
    public String getTranslatedSegment() { return translatedSegment; }
    public void setTranslatedSegment(String translatedSegment) { this.translatedSegment = translatedSegment; }
    public String getEngineType() { return engineType; }
    public void setEngineType(String engineType) { this.engineType = engineType; }
    public String getSourceLanguage() { return sourceLanguage; }
    public void setSourceLanguage(String sourceLanguage) { this.sourceLanguage = sourceLanguage; }
    public String getTargetLanguage() { return targetLanguage; }
    public void setTargetLanguage(String targetLanguage) { this.targetLanguage = targetLanguage; }
    public LocalDateTime getTranslatedAt() { return translatedAt; }
    public void setTranslatedAt(LocalDateTime translatedAt) { this.translatedAt = translatedAt; }
}
