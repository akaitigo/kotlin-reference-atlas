plugins {
    alias(libs.plugins.kotlin.jvm)
}

kotlin {
    compilerOptions {
        freeCompilerArgs.add("-Xmetadata-version=999.0.0")
        freeCompilerArgs.add("-Xgenerate-strict-metadata-version")
    }
}
