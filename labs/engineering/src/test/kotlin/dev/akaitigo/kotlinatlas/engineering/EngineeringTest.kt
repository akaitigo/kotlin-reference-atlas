// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.engineering

import java.nio.file.Path
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class EngineeringTest {
    @Test
    fun `failure classification preserves causal type for debugging`() {
        val cause = java.io.IOException("disk")
        val diagnostic = classifyFailure(IllegalStateException("write failed", cause))
        assertEquals("state", diagnostic.category)
        assertEquals("java.io.IOException", diagnostic.causeType)
    }

    @Test
    fun `security boundary only permits https allowlist without user info`() {
        assertEquals("kotlinlang.org", requireHttpsHost("https://kotlinlang.org/docs/home.html", setOf("kotlinlang.org")).host)
        assertThrows(IllegalArgumentException::class.java) { requireHttpsHost("http://kotlinlang.org", setOf("kotlinlang.org")) }
        assertThrows(IllegalArgumentException::class.java) { requireHttpsHost("https://evil.example", setOf("kotlinlang.org")) }
        assertThrows(IllegalArgumentException::class.java) { requireHttpsHost("https://user@kotlinlang.org", setOf("kotlinlang.org")) }
    }

    @Test
    fun `path traversal cannot escape operation root`() {
        val root = Path.of("build", "sandbox")
        assertTrue(resolveInside(root, "reports/result.json").endsWith("reports/result.json"))
        assertThrows(IllegalArgumentException::class.java) { resolveInside(root, "../../secret") }
    }

    @Test
    fun `constant-time primitive reports equality without text conversion`() {
        assertTrue(constantTimeEquals(byteArrayOf(1, 2), byteArrayOf(1, 2)))
        assertFalse(constantTimeEquals(byteArrayOf(1, 2), byteArrayOf(1, 3)))
    }

    @Test
    fun `migration accepts v1 and v2 and rejects unknown schema`() {
        assertEquals(DocumentV2("atlas", true), migrateDocument(mapOf("version" to "1", "name" to "atlas")))
        assertEquals(DocumentV2("atlas", false), migrateDocument(mapOf("version" to "2", "name" to "atlas", "enabled" to "false")))
        assertThrows(IllegalStateException::class.java) { migrateDocument(mapOf("version" to "3", "name" to "atlas")) }
    }

    @Test
    fun `performance harness emits finite median checksum and sample count`() {
        val result = benchmarkSum(size = 10_000)
        assertTrue(result.medianNanos > 0)
        assertEquals(50_005_000L, result.checksum)
        assertEquals(7, result.samples)
    }

    @Test
    fun `operation lifecycle supports failure recovery and stop`() {
        val lifecycle = ServiceLifecycle()
        lifecycle.dependenciesReady()
        lifecycle.dependencyFailed()
        assertEquals(ServiceState.DEGRADED, lifecycle.state)
        lifecycle.recovered()
        assertEquals(ServiceState.READY, lifecycle.state)
        lifecycle.stop()
        assertEquals(ServiceState.STOPPED, lifecycle.state)
    }
}
