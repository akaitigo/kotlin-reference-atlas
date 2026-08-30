// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ValueClassSecurityTest {
    @Test
    fun `foundations mechanics preserves trusted identity at a generic boxing boundary`() {
        val observation = observeBoundary("tok_12345678")

        assertTrue(observation.accepted)
        assertEquals(observation.token, observation.genericRoundTrip)
        assertTrue(observation.runtimeShape.isNotBlank())
        assertFalse(observeBoundary("../../secret").accepted)
    }

    @Test
    fun `compatibility integration keeps expect actual value representation executable`() {
        val observation = observeBoundary("tok_compat01")

        assertTrue(observation.accepted)
        assertTrue(observation.platform in setOf("jvm-openjdk17", "js-ir-node", "wasm-js-node", "native-macos-arm64"))
        assertEquals(SecureToken("tok_compat01"), observation.genericRoundTrip)
    }

    @Test
    fun `performance capacity cost boundary remains deterministic under repetition`() {
        val observations = (1..256).map { observeBoundary("tok_00000000$it") }

        assertTrue(observations.all(BoundaryObservation::accepted))
        assertEquals(256, observations.map(BoundaryObservation::genericRoundTrip).distinct().size)
        assertTrue(observations.all { it.runtimeShape.isNotBlank() })
    }
}
