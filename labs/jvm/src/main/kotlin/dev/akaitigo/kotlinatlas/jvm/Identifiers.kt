// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.jvm

@JvmInline
value class UserId(val value: String)

@JvmInline
value class WorkflowId(val value: String)

fun userLabel(id: UserId): String = "user:${id.value}"

fun runtimeTypeAtGenericBoundary(value: Any): String = value::class.qualifiedName.orEmpty()
