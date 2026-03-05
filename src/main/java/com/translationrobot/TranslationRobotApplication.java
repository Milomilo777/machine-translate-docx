package com.translationrobot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.web.client.RestTemplate;

@SpringBootApplication
@EnableAsync // Engineering Constraint: Parallelism - Enables @Async method execution
public class TranslationRobotApplication {

	public static void main(String[] args) {
		SpringApplication.run(TranslationRobotApplication.class, args);
	}

	/**
	 * Configures a RestTemplate bean for making HTTP requests to external APIs.
	 * In a production environment, consider using WebClient from Spring WebFlux
	 * for non-blocking I/O or Spring 6's RestClient for a more modern, synchronous approach.
	 */
	@Bean
	public RestTemplate restTemplate() {
		return new RestTemplate();
	}

	/*
	// Example CommandLineRunner to demonstrate triggering the async workflow:
	@Bean
	public CommandLineRunner runner(TranslationService translationService, DocumentRepository documentRepository) {
		return args -> {
			System.out.println("Application started. Creating a dummy document to trigger translation...");
			Document doc = new Document();
			doc.setContent("Hello world. How are you? This is a test document for translation into Spanish.");
			doc.setSourceLanguage("en");
			doc.setTargetLanguage("es");
			doc.setStatus(DocumentStatus.UPLOADED);
			doc = documentRepository.save(doc); // Save initial document
			System.out.println("Dummy Document created with ID: " + doc.getId());

			// Trigger the asynchronous translation process
			translationService.processDocument(doc.getId());
			System.out.println("Translation process initiated for document ID: " + doc.getId());
			// The main thread will continue, and the translation will happen in a separate thread.
		};
	}
	*/
}
