// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.runtime

import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

data class RuntimeRecord(val id: Int, val label: String = "default")

suspend fun resumedValue(value: String): String = suspendCoroutine { continuation -> continuation.resume(value) }

inline fun <reified T> filterRuntimeType(values: Iterable<Any>): List<T> = values.filterIsInstance<T>()

fun capturedClosure(base: Int): (Int) -> Int = { value -> base + value }
