package com.translationrobot.repository;

import com.translationrobot.model.Document;
import com.translationrobot.model.DocumentStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DocumentRepository extends JpaRepository<Document, Long> {
    List<Document> findByStatusIn(List<DocumentStatus> statuses);
}
