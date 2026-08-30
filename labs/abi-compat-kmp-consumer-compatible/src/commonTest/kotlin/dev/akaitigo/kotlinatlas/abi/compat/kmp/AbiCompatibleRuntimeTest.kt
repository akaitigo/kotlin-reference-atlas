// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat.kmp

import kotlin.test.Test
import kotlin.test.assertEquals

class AbiCompatibleRuntimeTest {
    @Test
    fun `unchanged consumer executes after a descriptor preserving migration`() {
        assertEquals("allow:reader", SecureConsumer.evaluateReader())
    }
}
