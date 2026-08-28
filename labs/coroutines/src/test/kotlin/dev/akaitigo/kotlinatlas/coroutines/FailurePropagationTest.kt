// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.coroutines

import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FailurePropagationTest {
    @Test
    fun `child failure cancels sibling and propagates to caller`() {
        var siblingCancelled = false

        val failure = assertFailsWith<IllegalStateException> {
            runBlocking {
                failWithWaitingSibling { siblingCancelled = true }
            }
        }

        assertEquals("primary-child-failure", failure.message)
        assertTrue(siblingCancelled)
    }
}
