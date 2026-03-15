package com.translationrobot.engine;

import com.translationrobot.engine.impl.ChatGptWebEngine;
import com.translationrobot.engine.impl.DeepLEngine;
import com.translationrobot.engine.impl.GoogleEngine;
import com.translationrobot.engine.impl.PerplexityEngine;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.concurrent.Semaphore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EngineSequentialGuardTest {

    @Test
    void googleEngine_HasSinglePermitRateLimiter() throws Exception {
        assertSinglePermitRateLimiter(GoogleEngine.class);
    }

    @Test
    void deepLEngine_HasSinglePermitRateLimiter() throws Exception {
        assertSinglePermitRateLimiter(DeepLEngine.class);
    }

    @Test
    void chatGptWebEngine_HasSinglePermitRateLimiter() throws Exception {
        assertSinglePermitRateLimiter(ChatGptWebEngine.class);
    }

    @Test
    void perplexityEngine_HasSinglePermitRateLimiter() throws Exception {
        assertSinglePermitRateLimiter(PerplexityEngine.class);
    }

    private void assertSinglePermitRateLimiter(Class<?> clazz) throws Exception {
        Field field = clazz.getDeclaredField("RATE_LIMITER");
        field.setAccessible(true);

        assertEquals(Semaphore.class, field.getType());
        assertTrue(Modifier.isStatic(field.getModifiers()));

        Semaphore semaphore = (Semaphore) field.get(null);
        assertEquals(1, semaphore.availablePermits());
    }
}
