import org.gradle.api.tasks.testing.logging.TestExceptionFormat
import org.jetbrains.kotlin.gradle.targets.js.nodejs.NodeJsEnvSpec
import org.jetbrains.kotlin.gradle.targets.js.nodejs.NodeJsPlugin
import org.jetbrains.kotlin.gradle.targets.wasm.nodejs.WasmNodeJsEnvSpec
import org.jetbrains.kotlin.gradle.targets.wasm.nodejs.WasmNodeJsPlugin

plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.multiplatform) apply false
}

allprojects {
    group = "dev.akaitigo.kotlinatlas"
    version = "0.2.0"

    dependencyLocking {
        lockAllConfigurations()
    }

    plugins.withType<NodeJsPlugin> {
        extensions.configure<NodeJsEnvSpec> {
            download.set(false)
            command.set(providers.environmentVariable("ATLAS_NODE").orElse("node"))
        }
    }

    plugins.withType<WasmNodeJsPlugin> {
        extensions.configure<WasmNodeJsEnvSpec> {
            download.set(false)
            command.set(providers.environmentVariable("ATLAS_NODE").orElse("node"))
        }
    }
}

subprojects {
    tasks.withType<Test>().configureEach {
        useJUnitPlatform()
        testLogging {
            events("failed", "skipped")
            exceptionFormat = TestExceptionFormat.FULL
        }
    }
}

tasks.register("atlasCheck") {
    group = "verification"
    description = "全Kotlin Labを実行する。"
    dependsOn(
        ":labs:jvm:test",
        ":labs:semantics:test",
        ":labs:coroutines:test",
        ":labs:flow:test",
        ":labs:interop:test",
        ":labs:gradle-plugin:test",
        ":labs:compiler-runtime:test",
        ":labs:engineering:test",
        ":labs:multiplatform:jvmTest",
        ":labs:multiplatform:jsNodeTest",
        ":labs:multiplatform:wasmJsNodeTest",
        ":labs:multiplatform:compileTestKotlinMacosArm64",
        ":reference-systems:automation-workbench:test",
        ":reference-systems:automation-workbench:captureRuntimeTrace",
    )
}
