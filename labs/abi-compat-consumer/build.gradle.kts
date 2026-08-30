import org.gradle.api.tasks.testing.Test
import org.gradle.jvm.tasks.Jar

plugins {
    alias(libs.plugins.kotlin.jvm)
}

dependencies {
    compileOnly(project(":labs:abi-compat-api-v1"))
    testImplementation(kotlin("test"))
}

val testSourceSet = sourceSets.named("test")

fun registerAbiTest(taskName: String, testClass: String, apiProject: String) =
    tasks.register<Test>(taskName) {
        group = "verification"
        description = "v1でcompileしたconsumerを $apiProject の実JVM artifactで検証する。"
        val apiJar = project(apiProject).tasks.named<Jar>("jar")
        dependsOn(tasks.named("testClasses"), apiJar)
        testClassesDirs = testSourceSet.get().output.classesDirs
        classpath = testSourceSet.get().runtimeClasspath + files(apiJar.flatMap { it.archiveFile })
        filter {
            includeTestsMatching(testClass)
        }
    }

val compatibilityBaselineTest = registerAbiTest(
    "compatibilityBaselineTest",
    "dev.akaitigo.kotlinatlas.abi.compat.CompatibilityBaselineTest",
    ":labs:abi-compat-api-v1",
)
val compatibilityBreakingTest = registerAbiTest(
    "compatibilityBreakingTest",
    "dev.akaitigo.kotlinatlas.abi.compat.CompatibilityBreakingTest",
    ":labs:abi-compat-api-v2-breaking",
)
val migrationBreakingTest = registerAbiTest(
    "migrationBreakingTest",
    "dev.akaitigo.kotlinatlas.abi.compat.MigrationBreakingTest",
    ":labs:abi-compat-api-v2-breaking",
)
val migrationCompatibleTest = registerAbiTest(
    "migrationCompatibleTest",
    "dev.akaitigo.kotlinatlas.abi.compat.MigrationCompatibleTest",
    ":labs:abi-compat-api-v2-compatible",
)

tasks.register("abiCompatibilityRuntimeTest") {
    group = "verification"
    dependsOn(compatibilityBaselineTest, compatibilityBreakingTest, migrationBreakingTest, migrationCompatibleTest)
}
