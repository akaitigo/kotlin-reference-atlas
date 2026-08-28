// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.flow

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.retry
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class FlowPipelinesTest {
    @Test
    fun `cold flow preserves normalized order`() = runBlocking {
        assertEquals(listOf("a", "b"), normalizedEvents(listOf(" A ", "", "B")).toList())
    }

    @Test
    fun `retry re-collects upstream until success`() = runBlocking {
        val attempts = mutableListOf<Int>()
        assertEquals("ready", failThenSucceed(attempts).retry(2).first())
        assertEquals(listOf(1, 2, 3), attempts)
    }

    @Test
    fun `state flow exposes latest state to a new consumer`() = runBlocking {
        val state = MutableStateFlow("starting")
        state.value = "ready"
        assertEquals("ready", state.first())
    }

    @Test
    fun `collector cancellation runs upstream finally`() = runBlocking {
        var cleaned = false
        val job = launch {
            try {
                normalizedEvents(List(100) { it.toString() }).collect { delay(10) }
            } finally {
                cleaned = true
            }
        }
        delay(20)
        job.cancelAndJoin()
        assertTrue(cleaned)
        assertTrue(job.isCancelled)
    }

    @Test
    fun `cancellation is not converted into a domain value`() = runBlocking {
        val job = launch { normalizedEvents(listOf("x")).collect { throw CancellationException("stop") } }
        job.join()
        assertTrue(job.isCancelled)
    }
}
