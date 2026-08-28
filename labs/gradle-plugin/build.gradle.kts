import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlin.jvm)
    `java-gradle-plugin`
}

kotlin {
    jvmToolchain(17)
    compilerOptions {
        jvmTarget = JvmTarget.JVM_17
        allWarningsAsErrors = true
    }
}

gradlePlugin {
    plugins {
        create("atlasProbe") {
            id = "dev.akaitigo.kotlin-atlas-probe"
            implementationClass = "dev.akaitigo.kotlinatlas.gradle.AtlasProbePlugin"
            displayName = "Kotlin Atlas Probe Plugin"
            description = "Gradle TestKitでconsumer契約を検証する最小Plugin"
        }
    }
}

dependencies {
    testImplementation(gradleTestKit())
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testImplementation(kotlin("test-junit5"))
}
