// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.abi.compat.kmp

object SecureConsumer {
    fun evaluateReader(): String = SecurePolicy().authorize("reader")
}
