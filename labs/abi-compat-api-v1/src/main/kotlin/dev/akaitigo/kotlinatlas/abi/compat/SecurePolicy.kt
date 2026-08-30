// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat

class SecurePolicy {
    fun authorize(role: String): String = "allow:$role"
}
