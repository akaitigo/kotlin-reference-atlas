# Coverage Epoch 2026-08-28

## 固定対象

- Kotlin compiler / Kotlin Gradle Plugin: 2.4.10
- Gradle: 9.5.0
- kotlinx.coroutines: 1.11.0
- JVM bytecode target: 17
- Reference Atlas Core Definitive Gate v2: `1ea027babf3a8d6720ac617c56988e447695ba63`
- Gradle依存: `gradle.lockfile`と`gradle/verification-metadata.xml`でVersionとSHA-256を固定

## bounded v0.2.0で閉じた範囲

- 言語Semantics、型System、JVM value class、Compiler/Runtime形状とbytecode
- structured concurrency、Flowのretry/State/cancellation
- JVM/JS/Wasm runtime、Native test KLIB compile、Java consumer、expect/actual
- Gradle Plugin consumer、Toolchain Lock、Testing、Performance、Security、Failure/Debugging
- Compatibility/Migration、Lifecycle/Recovery、Local/Container profile
- Compiler/stdlib Inventory、transitive SPDX SBOM、Router Skill Eval

## Definitive v2で再開した範囲

公式Spec／Docs／KEEP／Compiler／stdlib／Native runtime／coroutines／serialization／Gradleから既存reference edgeとして69 Behaviorを分類した。これはAuthority本文全体の網羅抽出ではない。9 Sourceを7 unique Git documentへ正規化し、`repository-root`と`tracked-blob`の固定selectorから146146 raw anchor候補を列挙したが、全件`pending-human`でありDepth達成へ算入しない。`atlas/definitive/gap-ledger.yaml`の30 Gapを閉じ、Human decision後のSurface昇格、10 Scenario Matrix、実Runtime Evidenceが揃うまでは`incomplete`とする。

## Blockedと対象外

Full Xcode不在によりmacOS arm64 Native executable実行とSwift Export consumerは`blocked`です。KLIB compileは代替証拠にしません。Android SDK、Ktor、Spring、Compose等のFramework固有Surface、KSP/第三者Compiler Plugin固有APIはKotlin本体の責任から分離します。
