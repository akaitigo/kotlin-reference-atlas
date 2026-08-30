// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class CompatibilityBaselineTest {
    @Test
    fun `compatibility integration executes the v1 binary contract without privilege change`() {
        assertEquals("allow:reader", SecureConsumer.evaluateReader())
    }
}

class CompatibilityBreakingTest {
    @Test
    fun `compatibility integration rejects a binary incompatible producer`() {
        assertFailsWith<NoSuchMethodError> { SecureConsumer.evaluateReader() }
    }
}

class MigrationBreakingTest {
    @Test
    fun `migration evolution observes the removed descriptor as a linkage failure`() {
        assertFailsWith<NoSuchMethodError> { SecureConsumer.evaluateReader() }
    }
}

class MigrationCompatibleTest {
    @Test
    fun `migration evolution preserves the old descriptor during recovery`() {
        assertEquals("allow:reader", SecureConsumer.evaluateReader())
    }
}
