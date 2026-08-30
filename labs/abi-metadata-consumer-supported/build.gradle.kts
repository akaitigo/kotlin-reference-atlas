plugins {
    alias(libs.plugins.kotlin.jvm)
}

dependencies {
    implementation(project(":labs:abi-metadata-api-supported"))
    testImplementation(kotlin("test"))
}
