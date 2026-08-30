// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.compiler

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ReifiedSecurityBoundaryTest {
    @Test
    fun `foundations mechanics rejects a mismatched runtime type token`() {
        val principal = SecurePrincipal("usr_001", setOf("reader"))

        assertEquals(principal, trustedValue(principal, ::isAllowedPrincipal))
        assertNull(trustedValue<SecurePrincipal>("usr_001", ::isAllowedPrincipal))
        assertNull(trustedValue(SecurePrincipal("root", setOf("writer")), ::isAllowedPrincipal))
    }

    @Test
    fun `compatibility integration validates generic elements after outer type erasure`() {
        val principals = listOf(
            SecurePrincipal("usr_001", setOf("reader")),
            SecurePrincipal("usr_002", setOf("writer")),
        )

        assertEquals(principals, trustedList(principals, ::isAllowedPrincipal))
        assertNull(trustedList<SecurePrincipal>(listOf(principals.first(), "usr_002"), ::isAllowedPrincipal))
        assertNull(trustedList(listOf(SecurePrincipal("usr_003", setOf("admin"))), ::isAllowedPrincipal))
    }

    @Test
    fun `performance capacity cost keeps the reified refusal result deterministic`() {
        var accepted = 0
        var refused = 0
        repeat(512) { index ->
            val candidate: Any = if (index % 2 == 0) {
                SecurePrincipal("usr_$index", setOf("reader"))
            } else {
                "usr_$index"
            }
            if (trustedValue<SecurePrincipal>(candidate, ::isAllowedPrincipal) == null) refused++ else accepted++
        }

        assertEquals(256, accepted)
        assertEquals(256, refused)
    }
}
