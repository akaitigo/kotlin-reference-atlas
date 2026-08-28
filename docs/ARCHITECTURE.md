# Architecture

## 目的

固定したCoverage Epochに対して、Kotlinの技術的主張を一次資料、Capability、Proof Obligation、再実行可能なLab、Evidenceへ接続します。記事数やCode量を完成指標にしません。

## Canonical chain

```text
Authority Source
  -> Coverage Target
  -> Capability
  -> Claim
  -> Proof Obligation
  -> Lab / Oracle
  -> Evidence
  -> Router Skill Eval
  -> Completion Certificate
```

## Archetype Overlay

- `product`: Kotlin 2.4.10、Gradle 9.5.0、kotlinx.coroutines 1.11.0という固定製品Versionを検証する。
- `language-platform`: Kotlin/JVMの言語・Platform SurfaceとJava境界を検証する。

Kotlin固有情報をCore Schemaへ追加しません。Capability、Claim、Lab、Migration mappingとしてこのRepository内に保持します。

## 実行境界

Local profileはGradle Wrapperから4つのLabを実行します。Container profileはRequiredですが未実装であり、Completionを阻止します。外部Service、Cloud Asset、Credentialは使用しません。
