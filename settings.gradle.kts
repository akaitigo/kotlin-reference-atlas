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
    ":reference-systems:automation-workbench",
)
