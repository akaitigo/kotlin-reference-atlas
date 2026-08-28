// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.runtime

import kotlinx.coroutines.runBlocking
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class RuntimeShapesTest {
    @Test
    fun `data class supplies component copy equality and defaults`() {
        val record = RuntimeRecord(1)
        val (id, label) = record
        assertEquals(1, id)
        assertEquals("default", label)
        assertEquals(RuntimeRecord(1, "changed"), record.copy(label = "changed"))
    }

    @Test
    fun `suspend continuation resumes exactly once`() = runBlocking {
        assertEquals("resumed", resumedValue("resumed"))
    }

    @Test
    fun `reified filter keeps runtime-compatible values`() {
        assertEquals(listOf("a", "b"), filterRuntimeType<String>(listOf("a", 1, "b")))
    }

    @Test
    fun `capturing lambda preserves lexical value`() {
        val addTen = capturedClosure(10)
        assertEquals(15, addTen(5))
        assertTrue(addTen.javaClass.declaredFields.isNotEmpty())
    }
}
