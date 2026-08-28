// SPDX-License-Identifier: Apache-2.0
@file:JvmName("AtlasApi")

package dev.akaitigo.kotlinatlas.interop

@JvmOverloads
fun greet(name: String, punctuation: String = "!"): String = "Hello, $name$punctuation"

@Throws(IllegalArgumentException::class)
fun requireAlias(value: String): String {
    require(value.isNotBlank()) { "alias must not be blank" }
    return value.trim()
}
