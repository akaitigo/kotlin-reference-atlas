// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.compiler

data class SecurePrincipal(val id: String, val roles: Set<String>)

inline fun <reified T : Any> trustedValue(value: Any?, validator: (T) -> Boolean): T? {
    val typed = value as? T ?: return null
    return typed.takeIf(validator)
}

inline fun <reified E : Any> trustedList(value: Any?, validator: (E) -> Boolean): List<E>? {
    val list = value as? List<*> ?: return null
    val result = mutableListOf<E>()
    for (element in list) {
        val typed = element as? E ?: return null
        if (!validator(typed)) return null
        result += typed
    }
    return result
}

fun isAllowedPrincipal(principal: SecurePrincipal): Boolean =
    principal.id.startsWith("usr_") && principal.roles.isNotEmpty() && principal.roles.all { it in setOf("reader", "writer") }
