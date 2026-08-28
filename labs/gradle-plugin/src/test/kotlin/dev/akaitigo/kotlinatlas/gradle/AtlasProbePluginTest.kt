// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.gradle

import org.gradle.testkit.runner.GradleRunner
import org.gradle.testkit.runner.TaskOutcome
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AtlasProbePluginTest {
    @TempDir
    lateinit var projectDir: Path

    @Test
    fun `consumer build applies plugin and executes probe task`() {
        Files.writeString(projectDir.resolve("settings.gradle.kts"), "rootProject.name = \"consumer-fixture\"\n")
        Files.writeString(
            projectDir.resolve("build.gradle.kts"),
            "plugins { id(\"dev.akaitigo.kotlin-atlas-probe\") }\n",
        )

        val result = GradleRunner.create()
            .withProjectDir(projectDir.toFile())
            .withArguments("atlasProbe", "--stacktrace")
            .withPluginClasspath()
            .build()

        assertEquals(TaskOutcome.SUCCESS, result.task(":atlasProbe")?.outcome)
        assertTrue(result.output.contains("atlas-probe:consumer-fixture"))
    }
}
