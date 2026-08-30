// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.metadata.kmp

object MetadataConsumer {
    fun evaluateReader(): String = MetadataPolicy().authorize("reader")
}
