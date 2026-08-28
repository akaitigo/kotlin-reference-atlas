import org.gradle.api.tasks.testing.logging.TestExceptionFormat

plugins {
    alias(libs.plugins.kotlin.jvm) apply false
}

allprojects {
    group = "dev.akaitigo.kotlinatlas"
    version = "0.1.0"

    dependencyLocking {
        lockAllConfigurations()
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
    dependsOn(subprojects.map { it.tasks.named("test") })
}
