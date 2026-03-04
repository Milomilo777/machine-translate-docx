package com.translationrobot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.EnableAspectJAutoProxy; // Not strictly needed for this task, but common for Spring apps

@SpringBootApplication
@EnableAspectJAutoProxy(proxyTargetClass = true) // Example if you use AOP
public class TranslationRobotApplication {

    public static void main(String[] args) {
        SpringApplication.run(TranslationRobotApplication.class, args);
    }
}
