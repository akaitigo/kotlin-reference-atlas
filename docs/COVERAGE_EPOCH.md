# Coverage Epoch 2026-08-28

## 固定対象

- Kotlin compiler / Kotlin Gradle Plugin: 2.4.10
- Gradle: 9.5.0
- kotlinx.coroutines: 1.11.0
- JVM bytecode target: 17
- Reference Atlas Core: `d5c0a6ce757fd5f43af837edd26f55c7325b811e`
- Gradle依存: `gradle.lockfile`と`gradle/verification-metadata.xml`でVersionとSHA-256を固定

## 今回閉じる範囲

- 言語Semantics、型System、JVM value class、Compiler/Runtime形状とbytecode
- structured concurrency、Flowのretry/State/cancellation
- JVM/JS/Wasm runtime、Native test KLIB compile、Java consumer、expect/actual
- Gradle Plugin consumer、Toolchain Lock、Testing、Performance、Security、Failure/Debugging
- Compatibility/Migration、Lifecycle/Recovery、Local/Container profile
- Compiler/stdlib Inventory、transitive SPDX SBOM、Router Skill Eval

## Infeasibleと対象外

Full Xcode不在によりmacOS arm64 Native executable実行とSwift Export consumerは`infeasible`です。Android SDK、Ktor、Spring、Compose等のFramework固有Surface、KSP/第三者Compiler Plugin固有APIはKotlin本体の責任から分離します。
