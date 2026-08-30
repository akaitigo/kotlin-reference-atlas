plugins {
    alias(libs.plugins.kotlin.jvm)
}

kotlin {
    jvmToolchain(17)
    compilerOptions.allWarningsAsErrors.set(true)
}

dependencies {
    implementation(libs.coroutines.core)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testImplementation(kotlin("test-junit5"))
}

val runtimeTrace = layout.buildDirectory.file("evidence/runtime-trace.tsv")

tasks.register<JavaExec>("captureRuntimeTrace") {
    group = "verification"
    description = "Automation Workbenchの実Runtime traceを生成する。"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("dev.akaitigo.kotlinatlas.workbench.EvidenceScenarioRunnerKt")
    args(runtimeTrace.get().asFile.absolutePath)
    outputs.file(runtimeTrace)
}
