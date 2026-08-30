// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi

actual value class SecureToken(actual val value: String)

actual fun platformIdentity(): String = "native-macos-arm64"

actual fun runtimeBoundaryShape(token: SecureToken): String = "native-value:${token.value.length}"
