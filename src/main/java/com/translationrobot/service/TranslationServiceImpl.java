package com.translationrobot.service;

import com.translationrobot.model.Translation;
import com.translationrobot.repository.TranslationRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional
public class TranslationServiceImpl implements TranslationService {

    private final TranslationRepository translationRepository;

    public TranslationServiceImpl(TranslationRepository translationRepository) {
        this.translationRepository = translationRepository;
    }

    @Override
    @Transactional(readOnly = true)
    public List<Translation> getTranslationsByDocument(Long documentId) {
        return translationRepository.findByDocumentId(documentId);
    }
}
