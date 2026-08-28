// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.platform

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class PlatformContractTest {
    @Test
    fun common_semantics_are_deterministic() {
        assertEquals(PortableRecord(7, listOf("jvm", "kotlin")), canonicalRecord(7, listOf(" kotlin ", "", "jvm")))
    }

    @Test
    fun platform_actual_is_linked_and_executed() {
        assertTrue(platformId() in setOf("jvm", "js", "wasm-js", "macos-arm64"), platformId())
    }
}
