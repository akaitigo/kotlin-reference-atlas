// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.kotlinatlas.gradle

import org.gradle.api.Plugin
import org.gradle.api.Project

class AtlasProbePlugin : Plugin<Project> {
    override fun apply(project: Project) {
        project.tasks.register("atlasProbe") { task ->
            task.group = "verification"
            task.description = "Kotlin Atlas Gradle Pluginのconsumer契約を検証する。"
            task.doLast {
                println("atlas-probe:${project.name}")
            }
        }
    }
}
