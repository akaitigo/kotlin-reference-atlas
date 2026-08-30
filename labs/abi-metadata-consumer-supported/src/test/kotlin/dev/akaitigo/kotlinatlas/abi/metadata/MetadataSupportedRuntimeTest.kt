// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.metadata

import kotlin.test.Test
import kotlin.test.assertEquals

class MetadataSupportedRuntimeTest {
    @Test
    fun `supported metadata executes with the security contract intact`() {
        assertEquals("allow:reader", MetadataConsumer.evaluateReader())
    }
}
