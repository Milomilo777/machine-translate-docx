package com.translationrobot.model;

import com.translationrobot.model.enums.DocumentStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import java.sql.Timestamp;
import java.util.Objects;
import java.util.UUID;

/**
 * Represents a document uploaded for machine translation.
 */
@Entity
@Table(name = "documents")
public class Document {

    @Id
    @Column(name = "id", updatable = false, nullable = false, columnDefinition = "BINARY(16)")
    private UUID id;

    @Column(name = "original_file_name", nullable = false)
    private String originalFileName;

    @Column(name = "file_type", nullable = false, length = 10) // e.g., "docx", "pdf", "txt"
    private String fileType;

    @CreationTimestamp // Automatically sets the creation timestamp by Hibernate
    @Column(name = "upload_date", nullable = false, updatable = false)
    private Timestamp uploadDate;

    @Enumerated(EnumType.STRING) // Stores the enum name as a String in the database
    @Column(name = "status", nullable = false)
    private DocumentStatus status;

    /**
     * Default constructor for JPA.
     */
    public Document() {
        // JPA requires a no-arg constructor
    }

    /**
     * Constructor for creating a new Document instance.
     * Generates a UUID for the ID.
     *
     * @param originalFileName The original name of the uploaded file.
     * @param fileType The file type (e.g., "docx").
     * @param status The current status of the document.
     */
    public Document(String originalFileName, String fileType, DocumentStatus status) {
        this.id = UUID.randomUUID(); // Application-level UUID generation
        this.originalFileName = originalFileName;
        this.fileType = fileType;
        this.status = status;
    }

    // --- Getters and Setters ---
    public UUID getId() {
        return id;
    }

    // ID is typically immutable after creation, no setter needed for application-managed UUID
    // public void setId(UUID id) { this.id = id; }

    public String getOriginalFileName() {
        return originalFileName;
    }

    public void setOriginalFileName(String originalFileName) {
        this.originalFileName = originalFileName;
    }

    public String getFileType() {
        return fileType;
    }

    public void setFileType(String fileType) {
        this.fileType = fileType;
    }

    public Timestamp getUploadDate() {
        return uploadDate;
    }

    // Upload date is automatically set on creation, no setter for direct modification
    // public void setUploadDate(Timestamp uploadDate) { this.uploadDate = uploadDate; }

    public DocumentStatus getStatus() {
        return status;
    }

    public void setStatus(DocumentStatus status) {
        this.status = status;
    }

    // --- Equals and HashCode ---
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

    // --- ToString ---
    @Override
    public String toString() {
        return "Document{" +
               "id=" + id +
               ", originalFileName='" + originalFileName + '\'' +
               ", fileType='" + fileType + '\'' +
               ", uploadDate=" + uploadDate +
               ", status=" + status +
               '}';
    }
}
