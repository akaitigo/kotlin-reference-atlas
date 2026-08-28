// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.workbench

import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.nio.file.Files
import java.nio.file.Path
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

private data class Trace(
    val scenario: String,
    val variant: String,
    val events: String,
    val outcome: String,
    val artifactDigest: String = "-",
    val health: String = "-",
)

fun main(arguments: Array<String>) = runBlocking {
    require(arguments.size == 1) { "runtime trace output path is required" }
    val fixedClock = Clock.fixed(Instant.parse("2026-08-28T00:00:00Z"), ZoneOffset.UTC)
    val traces = mutableListOf<Trace>()

    val normal = AutomationWorkbench(echoStep("done"), clock = fixedClock)
    val normalEvents = normal.execute(request("normal", "task"), InputPolicy.STRICT)
    val normalArtifact = (normalEvents.last() as WorkbenchEvent.Completed).artifact
    traces += Trace("normal", "strict", names(normalEvents), "completed", normalArtifact.digest, health(normal))

    val strict = AutomationWorkbench(echoStep(), clock = fixedClock)
    val strictEvents = strict.execute(request("strict", " Task "), InputPolicy.STRICT)
    traces += Trace("boundary", "strict", names(strictEvents), "rejected", health = health(strict))

    val normalize = AutomationWorkbench(echoStep(), clock = fixedClock)
    val normalizeEvents = normalize.execute(request("normalize", " Task "), InputPolicy.NORMALIZE)
    val normalizedArtifact = (normalizeEvents.last() as WorkbenchEvent.Completed).artifact
    traces += Trace("boundary", "normalize", names(normalizeEvents), normalizedArtifact.normalizedPayload, normalizedArtifact.digest, health(normalize))

    val recovery = AutomationWorkbench(
        step = object : WorkflowStep {
            override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                if (attempt == 1) throw TransientStepFailure("retry")
                return payload
            }
        },
        clock = fixedClock,
    )
    val recoveryEvents = recovery.execute(request("recovery", "task"), InputPolicy.STRICT)
    val recoveredArtifact = (recoveryEvents.last() as WorkbenchEvent.Completed).artifact
    traces += Trace("recovery", "bounded-retry", names(recoveryEvents), "completed", recoveredArtifact.digest, health(recovery))

    val permanent = AutomationWorkbench(
        step = object : WorkflowStep {
            override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String = error("broken")
        },
        clock = fixedClock,
    )
    val permanentEvents = permanent.execute(request("failure", "task"), InputPolicy.STRICT)
    traces += Trace("failure", "permanent", names(permanentEvents), (permanentEvents.last() as WorkbenchEvent.Failed).category, health = health(permanent))

    var calls = 0
    val duplicate = AutomationWorkbench(
        step = object : WorkflowStep {
            override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                calls += 1
                return payload
            }
        },
        clock = fixedClock,
    )
    val duplicateRequest = request("duplicate", "task")
    val first = duplicate.execute(duplicateRequest, InputPolicy.STRICT).last() as WorkbenchEvent.Completed
    val secondEvents = duplicate.execute(duplicateRequest, InputPolicy.STRICT)
    val second = secondEvents.single() as WorkbenchEvent.Completed
    check(first.artifact == second.artifact && calls == 1)
    traces += Trace("recovery", "idempotent-replay", names(secondEvents), "stored-artifact", second.artifact.digest, health(duplicate))

    val dispatcher = BoundedDispatcher(capacity = 1)
    val firstDispatch = dispatcher.submit(request("dispatch-first", "a"))
    val secondDispatch = dispatcher.submit(request("dispatch-second", "b"))
    dispatcher.receive()
    dispatcher.close()
    val closedDispatch = dispatcher.submit(request("dispatch-closed", "c"))
    traces += Trace("rejection", "bounded-channel", "$firstDispatch,$secondDispatch,$closedDispatch", "backpressure-then-closed")

    val entered = CompletableDeferred<Unit>()
    val cancellation = AutomationWorkbench(
        step = object : WorkflowStep {
            override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String {
                entered.complete(Unit)
                CompletableDeferred<Unit>().await()
                return payload
            }
        },
        clock = fixedClock,
    )
    val job = launch { cancellation.execute(request("cancellation", "task"), InputPolicy.STRICT) }
    entered.await()
    check(cancellation.health().active == 1)
    job.cancelAndJoin()
    check(job.isCancelled && cancellation.health() == WorkbenchHealth(0, 0, 0))
    traces += Trace("failure", "cancellation", "Accepted,Attempted,Cancelled", "propagated", health = health(cancellation))

    val content = buildString {
        appendLine("scenario\tvariant\tevents\toutcome\tartifact_digest\thealth")
        traces.forEach { trace ->
            appendLine(listOf(trace.scenario, trace.variant, trace.events, trace.outcome, trace.artifactDigest, trace.health).joinToString("\t"))
        }
    }
    val output = Path.of(arguments.single())
    Files.createDirectories(output.parent)
    Files.writeString(output, content)
    Unit
}

private fun request(id: String, payload: String) = WorkflowRequest(WorkflowId.parse(id), payload)

private fun echoStep(suffix: String? = null) = object : WorkflowStep {
    override suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int) =
        suffix?.let { "$payload:$it" } ?: payload
}

private fun names(events: List<WorkbenchEvent>) = events.joinToString(",") { it::class.simpleName ?: "Unknown" }

private fun health(workbench: AutomationWorkbench): String = workbench.health().let { "${it.active}/${it.completed}/${it.failed}" }
