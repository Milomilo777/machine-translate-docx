package com.translationrobot;

import com.translationrobot.gui.JavaFxApp;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);

        if (!java.awt.GraphicsEnvironment.isHeadless()) {
            javafx.application.Application.launch(JavaFxApp.class, args);
        }
    }
}
