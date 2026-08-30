// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi

@JvmInline
actual value class SecureToken(actual val value: String)

actual fun platformIdentity(): String = "jvm-openjdk17"

actual fun runtimeBoundaryShape(token: SecureToken): String = (token as Any)::class.qualifiedName.orEmpty()
