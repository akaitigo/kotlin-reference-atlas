// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.coroutines

import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch

suspend fun failWithWaitingSibling(onSiblingCancelled: () -> Unit): Nothing = coroutineScope {
    launch(start = CoroutineStart.UNDISPATCHED) {
        try {
            awaitCancellation()
        } finally {
            onSiblingCancelled()
        }
    }

    launch(start = CoroutineStart.UNDISPATCHED) {
        throw IllegalStateException("primary-child-failure")
    }

    awaitCancellation()
}
