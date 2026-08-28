// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.semantics

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertInstanceOf
import org.junit.jupiter.api.Test

class SemanticsTest {
    @Test
    fun `sealed result is exhaustively interpreted and smart-cast`() {
        assertEquals("value=7", describe(parsePositiveInt("7")))
        assertEquals("invalid=-1", describe(parsePositiveInt("-1")))
    }

    @Test
    fun `nothing failure is covariant with successful result type`() {
        val result: ParseResult<Number> = ParseResult.Failure("x")
        assertInstanceOf(ParseResult.Failure::class.java, result)
    }

    @Test
    fun `declaration-site variance permits safe producer and consumer substitution`() {
        val accepted = mutableListOf<Any>()
        val source: Source<String> = object : Source<String> { override fun next() = "kotlin" }
        val widerSink: Sink<String> = object : Sink<Any> { override fun accept(value: Any) { accepted += value } }
        transfer(source, widerSink)
        assertEquals(listOf("kotlin"), accepted)
    }

    @Test
    fun `reified parameter preserves runtime type token`() {
        assertEquals("kotlin.collections.List", runtimeTypeName<List<String>>())
    }

    @Test
    fun `lazy delegate initializes once`() {
        var calls = 0
        val probe = LazyProbe { calls += 1; "ready" }
        assertEquals(0, calls)
        assertEquals("ready", probe.value)
        assertEquals("ready", probe.value)
        assertEquals(1, calls)
    }

    @Test
    fun `sequence remains lazy until terminal operation`() {
        var reads = 0
        val values = listOf(1, 2, 3, 4).map { reads += 1; it }
        val sequence = evenSquares(values)
        assertEquals(4, reads)
        assertEquals(listOf(4, 16), sequence.toList())
    }
}
