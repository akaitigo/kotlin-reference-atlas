@file:OptIn(org.jetbrains.kotlin.gradle.ExperimentalWasmDsl::class)

plugins {
    alias(libs.plugins.kotlin.multiplatform)
}

kotlin {
    jvm()
    js { nodejs() }
    wasmJs { nodejs() }
    macosArm64()

    compilerOptions {
        freeCompilerArgs.add("-Xmetadata-version=999.0.0")
    }
}
