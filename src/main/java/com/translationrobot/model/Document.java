package com.translationrobot.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "documents")
public class Document {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID) // Engineering Constraint: UUIDs
    private UUID id;
    @Column(columnDefinition = "TEXT")
    private String content; // Original content
    @Enumerated(EnumType.STRING)
    private DocumentStatus status;
    private String sourceLanguage;
    private String targetLanguage;
    private LocalDateTime createdAt;
    private LocalDateTime lastUpdatedAt;

    public Document() {
        this.createdAt = LocalDateTime.now();
        this.lastUpdatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public DocumentStatus getStatus() { return status; }
    public void setStatus(DocumentStatus status) {
        this.status = status;
        this.lastUpdatedAt = LocalDateTime.now(); // Update lastUpdatedAt whenever status changes
    }
    public String getSourceLanguage() { return sourceLanguage; }
    public void setSourceLanguage(String sourceLanguage) { this.sourceLanguage = sourceLanguage; }
    public String getTargetLanguage() { return targetLanguage; }
    public void setTargetLanguage(String targetLanguage) { this.targetLanguage = targetLanguage; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public void setLastUpdatedAt(LocalDateTime lastUpdatedAt) { this.lastUpdatedAt = lastUpdatedAt; }
    public LocalDateTime getLastUpdatedAt() { return lastUpdatedAt; }
}
