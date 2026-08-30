// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi

actual value class SecureToken(actual val value: String)

actual fun platformIdentity(): String = "wasm-js-node"

actual fun runtimeBoundaryShape(token: SecureToken): String = "wasm-value:${token.value.length}"
