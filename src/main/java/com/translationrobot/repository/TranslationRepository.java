package com.translationrobot.repository;

import com.translationrobot.model.Translation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TranslationRepository extends JpaRepository<Translation, UUID> {
}
