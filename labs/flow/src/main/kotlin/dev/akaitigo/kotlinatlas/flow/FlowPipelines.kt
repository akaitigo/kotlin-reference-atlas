// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.flow

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow

fun normalizedEvents(inputs: List<String>): Flow<String> = flow {
    for (input in inputs) {
        val normalized = input.trim().lowercase()
        if (normalized.isNotEmpty()) emit(normalized)
    }
}

fun failThenSucceed(attempts: MutableList<Int>): Flow<String> = flow {
    val attempt = attempts.size + 1
    attempts += attempt
    if (attempt < 3) error("transient-$attempt")
    emit("ready")
}
