// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat

object SecureConsumer {
    fun evaluateReader(): String = SecurePolicy().authorize("reader")
}
