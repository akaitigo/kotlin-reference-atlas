// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.interop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class JavaConsumerTest {
    @Test
    void consumesJvmOverloadsFromJavaSource() {
        assertEquals("Hello, Ada!", AtlasApi.greet("Ada"));
        assertEquals("Hello, Ada?", AtlasApi.greet("Ada", "?"));
    }

    @Test
    void observesDeclaredExceptionContract() {
        assertEquals("atlas", AtlasApi.requireAlias(" atlas "));
        assertThrows(IllegalArgumentException.class, () -> AtlasApi.requireAlias(" "));
    }
}
