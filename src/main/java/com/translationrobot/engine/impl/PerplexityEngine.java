package com.translationrobot.engine.impl;

import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.springframework.stereotype.Component;

import org.openqa.selenium.By;
import org.openqa.selenium.Keys;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.interactions.Actions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.ThreadLocalRandom;

@Component
public class PerplexityEngine implements TranslationEngine {

    private static final java.util.concurrent.Semaphore RATE_LIMITER = new java.util.concurrent.Semaphore(1);

    public PerplexityEngine() {
        // No-arg constructor
    }

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.PERPLEXITY_WEB;
    }

    private void randomDelay() throws InterruptedException {
        long ms = 2000 + ThreadLocalRandom.current().nextLong(3000);
        Thread.sleep(ms);
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        try {
            RATE_LIMITER.acquire();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Thread interrupted while waiting for rate limiter", e);
        }

        try {
            long startTime = System.currentTimeMillis();

            int attempts = 0;
            while (attempts < 3) {
                WebDriver driver = null;
                try {
                    ChromeOptions options = new ChromeOptions();
                    options.addArguments("--disable-blink-features=AutomationControlled");
                    options.setExperimentalOption("excludeSwitches",
                            Collections.singletonList("enable-automation"));
                    options.addArguments("user-agent=Mozilla/5.0 (Windows NT 10.0; " +
                            "Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " +
                            "Chrome/122.0.0.0 Safari/537.36");

                    driver = new ChromeDriver(options);
                    randomDelay();
                    driver.get("https://www.perplexity.ai");
                    randomDelay();

                    String prompt = "Translate to " + targetLang +
                            ". Reply with translation only:\n" + text;

                    WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(15));
                    WebElement textarea = wait.until(
                            ExpectedConditions.presenceOfElementLocated(
                                    By.cssSelector("textarea[placeholder]")));

                    new Actions(driver).click(textarea)
                            .sendKeys(textarea, prompt).perform();
                    randomDelay();
                    textarea.sendKeys(Keys.RETURN);

                    WebDriverWait longWait = new WebDriverWait(driver,
                            Duration.ofSeconds(45));
                    longWait.until(ExpectedConditions.presenceOfElementLocated(
                            By.cssSelector("div.prose")));

                    WebElement response = driver.findElement(
                            By.cssSelector("div.prose"));
                    String result = response.getText();
                    randomDelay();

                    long endTime = System.currentTimeMillis();
                    double executionTimeSec = (endTime - startTime) / 1000.0;

                    return new TranslationResponse(result, 0, 0, 0.0, executionTimeSec);

                } catch (Exception e) {
                    attempts++;
                    if (attempts >= 3) {
                        throw new RuntimeException(
                                "Perplexity-Web: failed after 3 retries. " +
                                        "Last error: " + e.getMessage());
                    }
                    try {
                        Thread.sleep(45000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Interrupted during wait", ie);
                    }
                } finally {
                    if (driver != null) {
                        try {
                            driver.quit();
                        } catch (Exception ignored) {}
                    }
                }
            }
            return null;
        } finally {
            RATE_LIMITER.release();
        }
    }
}
