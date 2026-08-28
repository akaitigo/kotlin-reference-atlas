# Coverage Epoch 2026-08-28

## 固定対象

- Kotlin compiler / Kotlin Gradle Plugin: 2.4.10
- Gradle: 9.5.0
- kotlinx.coroutines: 1.11.0
- JVM bytecode target: 17
- Reference Atlas Core Definitive Gate v2: `be19ddaa411fe60dcf12f0f5d457902bb57b9eb3`
- Gradle依存: `gradle.lockfile`と`gradle/verification-metadata.xml`でVersionとSHA-256を固定

## bounded v0.2.0で閉じた範囲

- 言語Semantics、型System、JVM value class、Compiler/Runtime形状とbytecode
- structured concurrency、Flowのretry/State/cancellation
- JVM/JS/Wasm runtime、Native test KLIB compile、Java consumer、expect/actual
- Gradle Plugin consumer、Toolchain Lock、Testing、Performance、Security、Failure/Debugging
- Compatibility/Migration、Lifecycle/Recovery、Local/Container profile
- Compiler/stdlib Inventory、transitive SPDX SBOM、Router Skill Eval

## Definitive v2で再開した範囲

公式Spec／Docs／KEEP／Compiler／stdlib／Native runtime／coroutines／serialization／Gradleから69 Behaviorを導出した。`atlas/definitive/gap-ledger.yaml`の26 Gapを閉じ、10 Scenario Matrixと実Runtime Evidenceが揃うまでは`incomplete`とする。

## Blockedと対象外

Full Xcode不在によりmacOS arm64 Native executable実行とSwift Export consumerは`blocked`です。KLIB compileは代替証拠にしません。Android SDK、Ktor、Spring、Compose等のFramework固有Surface、KSP/第三者Compiler Plugin固有APIはKotlin本体の責任から分離します。
