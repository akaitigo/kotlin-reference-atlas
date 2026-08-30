@file:OptIn(org.jetbrains.kotlin.gradle.ExperimentalWasmDsl::class)

plugins {
    alias(libs.plugins.kotlin.multiplatform)
}

kotlin {
    jvm()
    js { nodejs() }
    wasmJs { nodejs() }
    macosArm64()

    sourceSets {
        commonMain.dependencies {
            implementation(project(":labs:abi-compat-kmp-api-v2-compatible"))
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
        }
    }
}
