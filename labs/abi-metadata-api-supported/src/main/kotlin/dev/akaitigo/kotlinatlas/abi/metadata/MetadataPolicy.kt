// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.metadata

class MetadataPolicy {
    fun authorize(role: String): String = "allow:$role"
}
