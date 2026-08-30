// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi

expect value class SecureToken(val value: String)

data class BoundaryObservation(
    val accepted: Boolean,
    val token: SecureToken,
    val genericRoundTrip: SecureToken,
    val platform: String,
    val runtimeShape: String,
)

private fun <T> genericBoundary(value: T): T = value

fun observeBoundary(raw: String): BoundaryObservation {
    val accepted = raw.startsWith("tok_") && raw.length in 8..64
    val token = SecureToken(if (accepted) raw else "tok_rejected")
    return BoundaryObservation(
        accepted = accepted,
        token = token,
        genericRoundTrip = genericBoundary(token),
        platform = platformIdentity(),
        runtimeShape = runtimeBoundaryShape(token),
    )
}

expect fun platformIdentity(): String

expect fun runtimeBoundaryShape(token: SecureToken): String
