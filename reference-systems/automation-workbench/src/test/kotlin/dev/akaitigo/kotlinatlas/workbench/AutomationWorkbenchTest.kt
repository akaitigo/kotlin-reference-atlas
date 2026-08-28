// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.workbench

import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertInstanceOf
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class AutomationWorkbenchTest {
    private val fixedClock = Clock.fixed(Instant.parse("2026-08-28T00:00:00Z"), ZoneOffset.UTC)

    @Test
    fun `normal execution emits context attempt and immutable artifact`() = runBlocking {
        val workbench = AutomationWorkbench(
            step = object : WorkflowStep {
                override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int) = "$payload:done"
            },
            clock = fixedClock,
        )

        val events = workbench.execute(request("alpha", "task"), InputPolicy.STRICT)

        assertEquals(listOf("Accepted", "Attempted", "Completed"), events.map { it::class.simpleName })
        val accepted = events[0] as WorkbenchEvent.Accepted
        assertEquals("workflow-alpha", accepted.contextName)
        val artifact = (events.last() as WorkbenchEvent.Completed).artifact
        assertEquals("task:done", artifact.normalizedPayload)
        assertEquals(64, artifact.digest.length)
        assertEquals(Instant.parse("2026-08-28T00:00:00Z"), artifact.completedAt)
        assertEquals(WorkbenchHealth(active = 0, completed = 1, failed = 0), workbench.health())
    }

    @Test
    fun `boundary policy compares strict rejection with normalization`() = runBlocking {
        val step = object : WorkflowStep {
            override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int) = payload
        }
        val strict = AutomationWorkbench(step, clock = fixedClock)
        val normalized = AutomationWorkbench(step, clock = fixedClock)

        assertInstanceOf(WorkbenchEvent.Rejected::class.java, strict.execute(request("strict", " Task "), InputPolicy.STRICT).single())
        val completed = normalized.execute(request("normalized", " Task "), InputPolicy.NORMALIZE).last() as WorkbenchEvent.Completed
        assertEquals("task", completed.artifact.normalizedPayload)
    }

    @Test
    fun `invalid identifier and attempt limit are rejected before execution`() = runBlocking {
        assertThrows(IllegalArgumentException::class.java) { WorkflowId.parse("UPPER") }
        val workbench = AutomationWorkbench(step = echoStep(), clock = fixedClock)
        assertThrows(IllegalArgumentException::class.java) {
            runBlocking { workbench.execute(request("valid", "task", maxAttempts = 0), InputPolicy.STRICT) }
        }
        Unit
    }

    @Test
    fun `transient failure recovers within bounded retry budget`() = runBlocking {
        val workbench = AutomationWorkbench(
            step = object : WorkflowStep {
                override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                    if (attempt == 1) throw TransientStepFailure("retry")
                    return payload
                }
            },
            clock = fixedClock,
        )

        val events = workbench.execute(request("recover", "task"), InputPolicy.STRICT)

        assertTrue(events.any { it is WorkbenchEvent.Recovered && it.failedAttempts == 1 })
        assertInstanceOf(WorkbenchEvent.Completed::class.java, events.last())
        Unit
    }

    @Test
    fun `permanent failure is categorized and observable`() = runBlocking {
        val workbench = AutomationWorkbench(
            step = object : WorkflowStep {
                override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String = error("broken")
            },
            clock = fixedClock,
        )

        val events = workbench.execute(request("failed", "task"), InputPolicy.STRICT)

        assertEquals("permanent", (events.last() as WorkbenchEvent.Failed).category)
        assertEquals(WorkbenchHealth(active = 0, completed = 0, failed = 1), workbench.health())
    }

    @Test
    fun `cancellation is not converted into failure and active gauge recovers`() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val workbench = AutomationWorkbench(
            step = object : WorkflowStep {
                override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                    entered.complete(Unit)
                    CompletableDeferred<Unit>().await()
                    return payload
                }
            },
            clock = fixedClock,
        )
        val job = launch { workbench.execute(request("cancelled", "task"), InputPolicy.STRICT) }
        entered.await()
        assertEquals(1, workbench.health().active)

        job.cancelAndJoin()

        assertTrue(job.isCancelled)
        assertEquals(WorkbenchHealth(active = 0, completed = 0, failed = 0), workbench.health())
    }

    @Test
    fun `bounded dispatcher exposes backpressure and closed recovery path`() = runBlocking {
        val dispatcher = BoundedDispatcher(capacity = 1)
        val first = request("first", "a")
        assertEquals(DispatchResult.Accepted, dispatcher.submit(first))
        assertEquals(DispatchResult.Backpressured, dispatcher.submit(request("second", "b")))
        assertEquals(first, dispatcher.receive())
        assertEquals(DispatchResult.Accepted, dispatcher.submit(request("second", "b")))
        dispatcher.close()
        assertEquals(DispatchResult.Closed, dispatcher.submit(request("third", "c")))
    }

    @Test
    fun `duplicate execution returns stored artifact without rerunning step`() = runBlocking {
        var calls = 0
        val workbench = AutomationWorkbench(
            step = object : WorkflowStep {
                override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                    calls += 1
                    return payload
                }
            },
            clock = fixedClock,
        )
        val request = request("duplicate", "task")

        val first = workbench.execute(request, InputPolicy.STRICT).last() as WorkbenchEvent.Completed
        val second = workbench.execute(request, InputPolicy.STRICT).single() as WorkbenchEvent.Completed

        assertEquals(first.artifact, second.artifact)
        assertEquals(1, calls)
    }

    @Test
    fun `migration normalizes legacy payload into current representation`() = runBlocking {
        val workbench = AutomationWorkbench(step = echoStep(), clock = fixedClock)
        val completed = workbench.execute(request("migration", " Legacy-Payload "), InputPolicy.NORMALIZE).last() as WorkbenchEvent.Completed
        assertEquals("legacy-payload", completed.artifact.normalizedPayload)
    }

    @Test
    fun `operations expose quiescent health after completion`() = runBlocking {
        val workbench = AutomationWorkbench(step = echoStep(), clock = fixedClock)
        workbench.execute(request("operations", "task"), InputPolicy.STRICT)
        assertEquals(WorkbenchHealth(active = 0, completed = 1, failed = 0), workbench.health())
    }

    @Test
    fun `security rejects traversal shaped workflow identity`() {
        assertThrows(IllegalArgumentException::class.java) { WorkflowId.parse("../escape") }
    }

    @Test
    fun `performance boundary keeps dispatcher capacity finite`() = runBlocking {
        val dispatcher = BoundedDispatcher(capacity = 1)
        assertEquals(DispatchResult.Accepted, dispatcher.submit(request("performance-first", "a")))
        assertEquals(DispatchResult.Backpressured, dispatcher.submit(request("performance-second", "b")))
    }

    @Test
    fun `compatibility records current JVM execution identity`() = runBlocking {
        val runtime = "java-${Runtime.version().feature()}"
        val workbench = AutomationWorkbench(step = echoStep(runtime), clock = fixedClock)
        val completed = workbench.execute(request("compatibility", "kotlin-2.4.10"), InputPolicy.STRICT).last() as WorkbenchEvent.Completed
        assertEquals("kotlin-2.4.10:$runtime", completed.artifact.normalizedPayload)
    }

    private fun request(id: String, payload: String, maxAttempts: Int = 2) =
        WorkflowRequest(WorkflowId.parse(id), payload, maxAttempts)

    private fun echoStep(suffix: String? = null) = object : WorkflowStep {
        override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int) = suffix?.let { "$payload:$it" } ?: payload
    }
}
