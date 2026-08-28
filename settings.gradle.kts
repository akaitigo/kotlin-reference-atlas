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
    ":labs:coroutines",
    ":labs:interop",
    ":labs:gradle-plugin",
)
