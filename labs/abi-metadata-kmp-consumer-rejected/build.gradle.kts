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
            implementation(project(":labs:abi-metadata-kmp-api-future"))
        }
    }
}
