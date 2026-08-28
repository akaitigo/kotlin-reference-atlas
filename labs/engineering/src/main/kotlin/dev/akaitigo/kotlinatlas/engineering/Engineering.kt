// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.engineering

import java.net.URI
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.system.measureNanoTime

data class Diagnostic(val category: String, val message: String, val causeType: String?)

fun classifyFailure(failure: Throwable): Diagnostic = Diagnostic(
    category = when (failure) {
        is IllegalArgumentException -> "input"
        is IllegalStateException -> "state"
        else -> "unexpected"
    },
    message = failure.message ?: failure::class.simpleName.orEmpty(),
    causeType = failure.cause?.javaClass?.name,
)

fun requireHttpsHost(raw: String, allowedHosts: Set<String>): URI {
    val uri = URI(raw)
    require(uri.scheme == "https") { "HTTPSが必要です" }
    require(uri.host in allowedHosts) { "許可されていないHostです" }
    require(uri.userInfo == null) { "User infoを含むURIは拒否します" }
    return uri
}

fun resolveInside(root: Path, requested: String): Path {
    val normalizedRoot = root.toAbsolutePath().normalize()
    val resolved = normalizedRoot.resolve(requested).normalize()
    require(resolved.startsWith(normalizedRoot)) { "Root外へのPath traversalを拒否します" }
    return resolved
}

fun constantTimeEquals(left: ByteArray, right: ByteArray): Boolean = MessageDigest.isEqual(left, right)

data class DocumentV2(val name: String, val enabled: Boolean)

fun migrateDocument(fields: Map<String, String>): DocumentV2 = when (fields["version"]) {
    "1" -> DocumentV2(name = fields.getValue("name"), enabled = true)
    "2" -> DocumentV2(name = fields.getValue("name"), enabled = fields.getValue("enabled").toBooleanStrict())
    else -> error("未対応Schema versionです: ${fields["version"]}")
}

data class BenchmarkResult(val medianNanos: Long, val checksum: Long, val samples: Int)

fun benchmarkSum(size: Int, samples: Int = 7): BenchmarkResult {
    require(size > 0 && samples >= 3)
    var checksum = 0L
    val durations = LongArray(samples) {
        measureNanoTime { checksum = (1..size).sumOf(Int::toLong) }
    }.sorted()
    return BenchmarkResult(durations[durations.size / 2], checksum, samples)
}

enum class ServiceState { STARTING, READY, DEGRADED, STOPPED }

class ServiceLifecycle {
    var state: ServiceState = ServiceState.STARTING
        private set

    fun dependenciesReady() { check(state == ServiceState.STARTING); state = ServiceState.READY }
    fun dependencyFailed() { check(state == ServiceState.READY); state = ServiceState.DEGRADED }
    fun recovered() { check(state == ServiceState.DEGRADED); state = ServiceState.READY }
    fun stop() { state = ServiceState.STOPPED }
}
