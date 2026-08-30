// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat.kmp

import kotlin.test.Test
import kotlin.test.assertEquals

class AbiBaselineRuntimeTest {
    @Test
    fun `unchanged consumer executes the version one security contract`() {
        assertEquals("allow:reader", SecureConsumer.evaluateReader())
    }
}
