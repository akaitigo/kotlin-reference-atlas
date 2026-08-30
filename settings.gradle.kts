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
    ":reference-systems:automation-workbench",
)
