package com.translationrobot;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ApplicationTest {

    @Test
    void hasJavaFxLaunchFlag_ReturnsFalseForEmptyArgs() {
        assertFalse(Application.hasJavaFxLaunchFlag(new String[]{}));
    }

    @Test
    void hasJavaFxLaunchFlag_ReturnsFalseForUnrelatedArgs() {
        assertFalse(Application.hasJavaFxLaunchFlag(new String[]{"--docxfile", "x.docx"}));
    }

    @Test
    void hasJavaFxLaunchFlag_ReturnsTrueForJavaFxFlag() {
        assertTrue(Application.hasJavaFxLaunchFlag(new String[]{"--javafx"}));
    }

    @Test
    void hasJavaFxLaunchFlag_ReturnsTrueForGuiFlag() {
        assertTrue(Application.hasJavaFxLaunchFlag(new String[]{"--gui"}));
    }
}
