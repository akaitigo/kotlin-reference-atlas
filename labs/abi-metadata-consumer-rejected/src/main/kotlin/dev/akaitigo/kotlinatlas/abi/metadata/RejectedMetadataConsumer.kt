// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.metadata

object RejectedMetadataConsumer {
    fun evaluateReader(): String = MetadataPolicy().authorize("reader")
}
