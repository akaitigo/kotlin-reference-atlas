pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
    }
}

rootProject.name = "kotlin-reference-atlas"

include(
    ":labs:jvm",
    ":labs:semantics",
    ":labs:coroutines",
    ":labs:flow",
    ":labs:interop",
    ":labs:gradle-plugin",
    ":labs:multiplatform",
    ":labs:compiler-runtime",
    ":labs:engineering",
    ":labs:abi-runtime-security",
    ":labs:abi-compat-api-v1",
    ":labs:abi-compat-api-v2-breaking",
    ":labs:abi-compat-api-v2-compatible",
    ":labs:abi-compat-consumer",
    ":labs:abi-metadata-api-supported",
    ":labs:abi-metadata-api-future",
    ":labs:abi-metadata-consumer-supported",
    ":labs:abi-metadata-consumer-rejected",
    ":labs:abi-metadata-consumer-override",
    ":reference-systems:automation-workbench",
)
