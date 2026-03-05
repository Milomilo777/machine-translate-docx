package com.translationrobot.exception;

public class TranslationApiException extends Exception {
    public TranslationApiException(String message) {
        super(message);
    }

    public TranslationApiException(String message, Throwable cause) {
        super(message, cause);
    }
}
