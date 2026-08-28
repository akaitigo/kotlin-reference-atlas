// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.workbench

import java.security.MessageDigest
import java.time.Clock
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineName
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

@JvmInline
value class WorkflowId private constructor(val value: String) {
    companion object {
        fun parse(raw: String): WorkflowId {
            require(raw.matches(Regex("[a-z0-9][a-z0-9-]{0,63}"))) { "workflow id is invalid" }
            return WorkflowId(raw)
        }
    }
}

data class WorkflowRequest(
    val id: WorkflowId,
    val payload: String,
    val maxAttempts: Int = 2,
)

enum class InputPolicy { STRICT, NORMALIZE }

sealed interface WorkbenchEvent {
    val workflowId: WorkflowId

    data class Accepted(override val workflowId: WorkflowId, val contextName: String) : WorkbenchEvent
    data class Attempted(override val workflowId: WorkflowId, val attempt: Int) : WorkbenchEvent
    data class Recovered(override val workflowId: WorkflowId, val failedAttempts: Int) : WorkbenchEvent
    data class Completed(override val workflowId: WorkflowId, val artifact: WorkflowArtifact) : WorkbenchEvent
    data class Rejected(override val workflowId: WorkflowId, val reason: String) : WorkbenchEvent
    data class Failed(override val workflowId: WorkflowId, val category: String) : WorkbenchEvent
}

data class WorkflowArtifact(
    val workflowId: WorkflowId,
    val normalizedPayload: String,
    val digest: String,
    val completedAt: Instant,
)

interface WorkflowStep {
    suspend fun execute(workflowId: WorkflowId, payload: String, attempt: Int): String
}

class TransientStepFailure(message: String) : RuntimeException(message)

class InMemoryArtifactStore {
    private val artifacts = ConcurrentHashMap<WorkflowId, WorkflowArtifact>()

    fun putIfAbsent(artifact: WorkflowArtifact): WorkflowArtifact =
        artifacts.putIfAbsent(artifact.workflowId, artifact) ?: artifact

    fun get(id: WorkflowId): WorkflowArtifact? = artifacts[id]
}

class AutomationWorkbench(
    private val step: WorkflowStep,
    private val store: InMemoryArtifactStore = InMemoryArtifactStore(),
    private val clock: Clock = Clock.systemUTC(),
) {
    private val locks = ConcurrentHashMap<WorkflowId, Mutex>()
    private val active = AtomicInteger()
    private val completed = AtomicInteger()
    private val failed = AtomicInteger()

    suspend fun execute(request: WorkflowRequest, policy: InputPolicy): List<WorkbenchEvent> =
        withContext(CoroutineName("workflow-${request.id.value}")) {
            require(request.maxAttempts in 1..5) { "maxAttempts must be between 1 and 5" }
            val normalized = normalize(request.payload, policy)
                ?: return@withContext listOf(WorkbenchEvent.Rejected(request.id, "payload is blank"))
            val lock = locks.computeIfAbsent(request.id) { Mutex() }
            lock.withLock {
                store.get(request.id)?.let { existing ->
                    return@withLock listOf(WorkbenchEvent.Completed(request.id, existing))
                }
                active.incrementAndGet()
                try {
                    runAttempts(request, normalized)
                } finally {
                    active.decrementAndGet()
                    locks.remove(request.id, lock)
                }
            }
        }

    fun health(): WorkbenchHealth = WorkbenchHealth(
        active = active.get(),
        completed = completed.get(),
        failed = failed.get(),
    )

    private suspend fun runAttempts(request: WorkflowRequest, normalized: String): List<WorkbenchEvent> {
        val contextName = currentCoroutineContext()[CoroutineName]?.name ?: "missing"
        val events = mutableListOf<WorkbenchEvent>(WorkbenchEvent.Accepted(request.id, contextName))
        for (attempt in 1..request.maxAttempts) {
            currentCoroutineContext().ensureActive()
            events += WorkbenchEvent.Attempted(request.id, attempt)
            try {
                val output = step.execute(request.id, normalized, attempt)
                currentCoroutineContext().ensureActive()
                val artifact = WorkflowArtifact(
                    workflowId = request.id,
                    normalizedPayload = output,
                    digest = sha256(output),
                    completedAt = clock.instant(),
                )
                val stored = store.putIfAbsent(artifact)
                if (attempt > 1) events += WorkbenchEvent.Recovered(request.id, attempt - 1)
                events += WorkbenchEvent.Completed(request.id, stored)
                completed.incrementAndGet()
                return events
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (transient: TransientStepFailure) {
                if (attempt == request.maxAttempts) {
                    failed.incrementAndGet()
                    events += WorkbenchEvent.Failed(request.id, "transient-exhausted")
                    return events
                }
                delay(1)
            } catch (failure: RuntimeException) {
                failed.incrementAndGet()
                events += WorkbenchEvent.Failed(request.id, "permanent")
                return events
            }
        }
        error("attempt loop must return")
    }

    private fun normalize(payload: String, policy: InputPolicy): String? = when (policy) {
        InputPolicy.STRICT -> payload.takeIf { it.isNotBlank() && it == it.trim() }
        InputPolicy.NORMALIZE -> payload.trim().lowercase().takeIf(String::isNotEmpty)
    }
}

data class WorkbenchHealth(val active: Int, val completed: Int, val failed: Int)

private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
    .digest(value.toByteArray(Charsets.UTF_8))
    .joinToString("") { byte -> "%02x".format(byte) }
