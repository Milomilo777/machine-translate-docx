package com.translationrobot.engine.impl;

import com.translationrobot.engine.TranslationEngine;
import com.translationrobot.model.EngineType;
import com.translationrobot.model.TranslationResponse;
import org.openqa.selenium.By;
import org.openqa.selenium.Keys;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.interactions.Actions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.ThreadLocalRandom;

@Component
public class ChatGptWebEngine implements TranslationEngine {

    @Override
    public boolean supports(EngineType type) {
        return type == EngineType.CHATGPT_WEB;
    }

    private void randomDelay() throws InterruptedException {
        long ms = 2000 + ThreadLocalRandom.current().nextLong(3000);
        Thread.sleep(ms);
    }

    @Override
    public TranslationResponse translate(String sourceLang, String targetLang, String text) {
        long startTime = System.currentTimeMillis();

        ChromeOptions options = new ChromeOptions();
        options.addArguments("--disable-blink-features=AutomationControlled");
        options.setExperimentalOption("excludeSwitches",
                Collections.singletonList("enable-automation"));
        options.addArguments("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36");

        int attempts = 0;
        WebDriver driver = null;

        while (attempts < 3) {
            try {
                driver = new ChromeDriver(options);
                randomDelay();
                driver.get("https://chatgpt.com");
                randomDelay();

                // Find textarea
                WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(15));
                WebElement textarea = wait.until(
                        ExpectedConditions.presenceOfElementLocated(
                                By.cssSelector("textarea#prompt-textarea")));

                // Build and type prompt
                String prompt = "Translate the following text to " + targetLang +
                        ". Return ONLY the translated text, no explanations:\n" + text;
                new Actions(driver).click(textarea).sendKeys(textarea, prompt).perform();
                randomDelay();

                // Submit
                textarea.sendKeys(Keys.RETURN);

                // Wait for response (max 60 seconds)
                WebDriverWait longWait = new WebDriverWait(driver, Duration.ofSeconds(60));
                longWait.until(ExpectedConditions.invisibilityOfElementLocated(
                        By.cssSelector("button[data-testid='stop-button']")));

                // Extract result
                WebElement response = driver.findElement(
                        By.cssSelector("div[data-message-author-role='assistant']:last-child"));
                String result = response.getText();
                randomDelay();

                long endTime = System.currentTimeMillis();
                double executionTimeSec = (endTime - startTime) / 1000.0;

                return new TranslationResponse(result, 0, 0, 0.0, executionTimeSec);
            } catch (Exception e) {
                attempts++;
                if (attempts >= 3) {
                    throw new RuntimeException(
                            "ChatGPT-Web: failed after 3 retries. Last error: " + e.getMessage());
                }
                try {
                    Thread.sleep(45000); // wait 45 sec before retry
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException("Interrupted during wait", ie);
                }
            } finally {
                if (driver != null) {
                    try {
                        driver.quit();
                    } catch (Exception ignored) {
                    }
                    driver = null; // Important to avoid re-using quit driver
                }
            }
        }
        return null; // unreachable but required by compiler
    }
}
