package com.translationrobot.model;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.Objects;

@Entity
@Table(name = "documents")
public class Document {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String originalFileName;
    private String fileType; // e.g., docx, pdf, txt
    private String sourceLanguage;
    private String targetLanguage;

    @Enumerated(EnumType.STRING)
    private DocumentStatus status;

    private LocalDateTime createdDate;
    private LocalDateTime updatedDate;

    public Document() {
        this.createdDate = LocalDateTime.now();
        this.updatedDate = LocalDateTime.now();
        this.status = DocumentStatus.PENDING;
    }

    // All-args constructor
    public Document(Long id, String originalFileName, String fileType, String sourceLanguage, String targetLanguage, DocumentStatus status, LocalDateTime createdDate, LocalDateTime updatedDate) {
        this.id = id;
        this.originalFileName = originalFileName;
        this.fileType = fileType;
        this.sourceLanguage = sourceLanguage;
        this.targetLanguage = targetLanguage;
        this.status = status;
        this.createdDate = createdDate;
        this.updatedDate = updatedDate;
    }

    // Constructor without ID for creation
    public Document(String originalFileName, String fileType, String sourceLanguage, String targetLanguage) {
        this(); // Call default constructor for dates and status
        this.originalFileName = originalFileName;
        this.fileType = fileType;
        this.sourceLanguage = sourceLanguage;
        this.targetLanguage = targetLanguage;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getOriginalFileName() { return originalFileName; }
    public void setOriginalFileName(String originalFileName) { this.originalFileName = originalFileName; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public String getSourceLanguage() { return sourceLanguage; }
    public void setSourceLanguage(String sourceLanguage) { this.sourceLanguage = sourceLanguage; }
    public String getTargetLanguage() { return targetLanguage; }
    public void setTargetLanguage(String targetLanguage) { this.targetLanguage = targetLanguage; }
    public DocumentStatus getStatus() { return status; }
    public void setStatus(DocumentStatus status) {
        this.status = status;
        this.updatedDate = LocalDateTime.now(); // Update timestamp on status change
    }
    public LocalDateTime getCreatedDate() { return createdDate; }
    public void setCreatedDate(LocalDateTime createdDate) { this.createdDate = createdDate; }
    public LocalDateTime getUpdatedDate() { return updatedDate; }
    public void setUpdatedDate(LocalDateTime updatedDate) { this.updatedDate = updatedDate; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Document document = (Document) o;
        return Objects.equals(id, document.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    @Override
    public String toString() {
        return "Document{" +
               "id=" + id +
               ", originalFileName='" + originalFileName + '\'' +
               ", fileType='" + fileType + '\'' +
               ", sourceLanguage='" + sourceLanguage + '\'' +
               ", targetLanguage='" + targetLanguage + '\'' +
               ", status=" + status +
               ", createdDate=" + createdDate +
               ", updatedDate=" + updatedDate +
               '}';
    }
}
