package com.translationrobot.repository;

import com.translationrobot.domain.Document;
import com.translationrobot.domain.enums.DocumentStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Spring Data JPA repository for the {@link Document} entity.
 * Provides standard CRUD operations and custom query methods for Document management.
 */
@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    /**
     * Retrieves a list of documents filtered by their processing status.
     *
     * @param status The {@link DocumentStatus} to filter by.
     * @return A list of {@link Document} entities matching the given status.
     */
    List<Document> findByStatus(DocumentStatus status);
}
