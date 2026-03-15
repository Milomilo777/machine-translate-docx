package com.translationrobot;

import com.translationrobot.gui.JavaFxApp;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);

        if (shouldLaunchJavaFx(args)) {
            javafx.application.Application.launch(JavaFxApp.class, args);
        }
    }

    static boolean hasJavaFxLaunchFlag(String[] args) {
        if (args == null) {
            return false;
        }

        for (String arg : args) {
            if ("--javafx".equals(arg) || "--gui".equals(arg)) {
                return true;
            }
        }

        return false;
    }

    static boolean shouldLaunchJavaFx(String[] args) {
        return !java.awt.GraphicsEnvironment.isHeadless() && hasJavaFxLaunchFlag(args);
    }
}
