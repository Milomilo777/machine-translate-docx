package com.translationrobot.repository;

import com.translationrobot.model.TranslationLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TranslationLogRepository extends JpaRepository<TranslationLog, UUID> {
}
