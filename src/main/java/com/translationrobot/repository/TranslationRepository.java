package com.translationrobot.repository;

import com.translationrobot.domain.Translation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

/**
 * Spring Data JPA repository for the {@link Translation} entity.
 * This repository ensures correct handling of large text segments (LOBs)
 * defined within the Translation model through standard JPA CRUD operations.
 */
@Repository
public interface TranslationRepository extends JpaRepository<Translation, UUID> {
    // Standard CRUD operations are inherited from JpaRepository.
    // LOB handling is configured within the Translation entity itself (from Phase 5).
}
