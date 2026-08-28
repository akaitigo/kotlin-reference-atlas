# Kotlin・Toolchain Migration Guide

## Epochを更新する条件

Kotlin、Kotlin Gradle Plugin、Gradle、kotlinx.coroutines、Node、Native Toolchainのいずれかを更新する場合は新しいCoverage Epochを作る。既存Evidenceを上書きして同じReleaseと扱わない。

## 手順

1. `sources.lock.yaml`へ新Artifact URL、Version、Digestを記録する。
2. `coverage.yaml.authority_lock_digest`を再計算する。
3. Version Catalog、Wrapper、Dependency Lock、verification metadataを更新する。
4. JVM/JS/Wasm実行とNative KLIB compileを行う。
5. Java consumer、Flow/cancellation、bytecode、Migration fixtureを実行する。
6. InventoryとSPDX SBOMを再生成し差分をReviewする。
7. Router Evalで旧Capability名やGap判定のdriftを確認する。
8. Local/Container profileを実行し、新しいCompletion Certificateを発行する。

## Compatibility分類

- Source：旧Sourceが新Compilerでcompileするか。
- Binary：公開JVM signatureと生成Memberが変化するか。
- Behavioral：Coroutine/Flow、default引数、exceptionの観測結果が変化するか。
- Tooling：Gradle task、Plugin ID、Lock形式、Node/Native setupが変化するか。
- Platform：commonTestがJVM/JS/Wasmで同じContractを満たすか。

未知Versionや未検証Platformを自動的にcompatibleと推測しない。
