// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.platform

expect fun platformId(): String

data class PortableRecord(val id: Int, val tags: List<String>)

fun canonicalRecord(id: Int, tags: List<String>): PortableRecord = PortableRecord(id, tags.map(String::trim).filter(String::isNotEmpty).sorted())
