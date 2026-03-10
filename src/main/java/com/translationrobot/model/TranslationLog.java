package com.translationrobot.model;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Column;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "queries")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TranslationLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "doc_id", length = 2048)
    private String docId;

    @Column(name = "model_name")
    private String modelName;

    @jakarta.persistence.Lob
    @Column(name = "prompt_json", columnDefinition="TEXT")
    private String promptJson;

    @jakarta.persistence.Lob
    @Column(name = "response_json", columnDefinition="TEXT")
    private String responseJson;

    @Column(name = "execution_time_sec")
    private double executionTimeSec;

    @Column(name = "input_tokens")
    private int inputTokens;

    @Column(name = "output_tokens")
    private int outputTokens;

    @Column(name = "total_tokens")
    private int totalTokens;

    @Column(name = "cost_usd")
    private double costUsd;
}
