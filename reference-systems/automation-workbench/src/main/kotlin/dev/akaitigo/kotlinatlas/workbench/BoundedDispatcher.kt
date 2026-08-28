// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.workbench

import kotlinx.coroutines.channels.Channel

sealed interface DispatchResult {
    data object Accepted : DispatchResult
    data object Backpressured : DispatchResult
    data object Closed : DispatchResult
}

class BoundedDispatcher(capacity: Int) {
    private val queue = Channel<WorkflowRequest>(capacity)

    init {
        require(capacity > 0) { "capacity must be positive" }
    }

    fun submit(request: WorkflowRequest): DispatchResult {
        val result = queue.trySend(request)
        return when {
            result.isSuccess -> DispatchResult.Accepted
            result.isClosed -> DispatchResult.Closed
            else -> DispatchResult.Backpressured
        }
    }

    suspend fun receive(): WorkflowRequest = queue.receive()

    fun close() = queue.close()
}
