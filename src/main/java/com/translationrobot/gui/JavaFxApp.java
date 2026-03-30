package com.translationrobot.gui;

import javafx.application.Application;
import javafx.scene.Scene;
import javafx.scene.control.Label;
import javafx.scene.layout.StackPane;
import javafx.stage.Stage;

public class JavaFxApp extends Application {

    @Override
    public void start(Stage stage) {
        Label label = new Label("SMTV Robot is Running\nWeb Interface: http://localhost:8080");
        label.setStyle("-fx-font-size: 16px; -fx-text-alignment: center;");

        StackPane root = new StackPane(label);
        Scene scene = new Scene(root, 400, 200);

        stage.setTitle("SMTV Translation Robot");
        stage.setScene(scene);
        stage.show();
    }
}
