// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.semantics

sealed interface ParseResult<out T> {
    data class Success<T>(val value: T) : ParseResult<T>
    data class Failure(val input: String) : ParseResult<Nothing>
}

fun parsePositiveInt(input: String): ParseResult<Int> {
    val value = input.toIntOrNull()
    return if (value != null && value > 0) ParseResult.Success(value) else ParseResult.Failure(input)
}

fun describe(result: ParseResult<Int>): String = when (result) {
    is ParseResult.Success -> "value=${result.value}"
    is ParseResult.Failure -> "invalid=${result.input}"
}

interface Source<out T> {
    fun next(): T
}

interface Sink<in T> {
    fun accept(value: T)
}

fun transfer(source: Source<String>, sink: Sink<String>) = sink.accept(source.next())

inline fun <reified T> runtimeTypeName(): String = T::class.qualifiedName ?: error("匿名型は対象外")

class LazyProbe(private val initializer: () -> String) {
    val value: String by lazy(initializer)
}

fun evenSquares(values: Iterable<Int>): Sequence<Int> = values.asSequence().filter { it % 2 == 0 }.map { it * it }
