package com.translationrobot.model;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.Objects;

@Entity
@Table(name = "translations")
public class Translation {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long documentId; // Foreign key to Document
    private String translatedText; // Or path to translated file
    private LocalDateTime translationDate;

    public Translation() {
        this.translationDate = LocalDateTime.now();
    }

    public Translation(Long id, Long documentId, String translatedText) {
        this();
        this.id = id;
        this.documentId = documentId;
        this.translatedText = translatedText;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getDocumentId() { return documentId; }
    public void setDocumentId(Long documentId) { this.documentId = documentId; }
    public String getTranslatedText() { return translatedText; }
    public void setTranslatedText(String translatedText) { this.translatedText = translatedText; }
    public LocalDateTime getTranslationDate() { return translationDate; }
    public void setTranslationDate(LocalDateTime translationDate) { this.translationDate = translationDate; }

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

    @Override
    public String toString() {
        return "Translation{" +
               "id=" + id +
               ", documentId=" + documentId +
               ", translatedText='" + translatedText + '\'' +
               ", translationDate=" + translationDate +
               '}';
    }
}
