// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.metadata

import kotlin.test.Test
import kotlin.test.assertEquals

class MetadataOverrideRuntimeTest {
    @Test
    fun `explicit metadata override remains bounded by the runtime security oracle`() {
        assertEquals("allow:reader", OverrideMetadataConsumer.evaluateReader())
    }
}
