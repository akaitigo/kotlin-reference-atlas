# Coverage Epoch 2026-08-28

## 固定対象

- Kotlin compiler / Kotlin Gradle Plugin: 2.4.10
- Gradle: 9.5.0
- kotlinx.coroutines: 1.11.0
- JVM bytecode target: 17
- Reference Atlas Core Definitive Gate v2: `7c9313cfb3e3149af455976228b44bbcb706bf40`
- Gradle依存: `gradle.lockfile`と`gradle/verification-metadata.xml`でVersionとSHA-256を固定

## bounded v0.2.0で閉じた範囲

- 言語Semantics、型System、JVM value class、Compiler/Runtime形状とbytecode
- structured concurrency、Flowのretry/State/cancellation
- JVM/JS/Wasm runtime、Native test KLIB compile、Java consumer、expect/actual
- Gradle Plugin consumer、Toolchain Lock、Testing、Performance、Security、Failure/Debugging
- Compatibility/Migration、Lifecycle/Recovery、Local/Container profile
- Compiler/stdlib Inventory、transitive SPDX SBOM、Router Skill Eval

## Definitive v2で再開した範囲

公式Spec／Docs／KEEP／Compiler／stdlib／Native runtime／coroutines／serialization／Gradleから既存reference edgeとして69 Behaviorを分類した。これはAuthority本文全体の網羅抽出ではない。18 Source Lock entryを16 documentへ正規化し、固定selectorから146393 candidate anchorを列挙して全件Review Queueへ割り当てたが、全件`pending-human`でありQueue件数はDepth達成へ算入しない。10 Scenario統合Traceと69×10専用rowは作成済みだが、4590 Surface×Scenario×Variant cellは全て専用実行未閉鎖の明示Gapで、Authority atomic／completion eligibleも0である。690未閉鎖rowはrisk順180 trancheのClosure Planへ固定した。`atlas/definitive/gap-ledger.yaml`の30 Gapを閉じ、Human decision後のSurface昇格と全適用cellの専用実Runtime Evidenceが揃うまでは`incomplete`とする。

## Blockedと対象外

Full Xcode不在によりmacOS arm64 Native executable実行とSwift Export consumerは`blocked`です。KLIB compileは代替証拠にしません。Android SDK、Ktor、Spring、Compose等のFramework固有Surface、KSP/第三者Compiler Plugin固有APIはKotlin本体の責任から分離します。
