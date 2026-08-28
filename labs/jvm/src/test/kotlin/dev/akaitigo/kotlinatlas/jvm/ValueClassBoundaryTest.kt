// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.jvm

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ValueClassBoundaryTest {
    @Test
    fun `source-level identifier remains distinct and usable`() {
        val userId = UserId("u-1")

        assertEquals("user:u-1", userLabel(userId))
    }

    @Test
    fun `value class is boxed at Any boundary`() {
        val runtimeType = runtimeTypeAtGenericBoundary(UserId("u-1"))

        assertTrue(runtimeType.endsWith(".UserId"), runtimeType)
    }
}
