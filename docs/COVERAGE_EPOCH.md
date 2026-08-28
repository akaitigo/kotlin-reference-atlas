# Coverage Epoch 2026-08-28

## 固定対象

- Kotlin compiler / Kotlin Gradle Plugin: 2.4.10
- Gradle: 9.5.0
- kotlinx.coroutines: 1.11.0
- JVM bytecode target: 17
- Reference Atlas Core: `d5c0a6ce757fd5f43af837edd26f55c7325b811e`
- Gradle依存: `gradle.lockfile`と`gradle/verification-metadata.xml`でVersionとSHA-256を固定

## 今回閉じる範囲

- JVM value classのsource-level型分離とgeneric境界のboxing
- Gradle Pluginの登録TaskをGradle TestKit consumer buildから実行
- structured concurrencyにおける子失敗、兄弟cancel、親への例外伝播
- Kotlin APIをJava consumerから呼び出すoverloadとchecked exception宣言
- Router SkillのCapability選択とCoverage gap応答
- Manifest、License、NOTICE、第三者ManifestのLocal gate

## 未完了

Kotlin言語・stdlib公開Surface全Inventory、Compiler diagnostics全件、KMP、Native、JS、Wasm、Android、Apple、TypeScript/C相互運用、KSP、Compiler Plugin、Benchmark、Container profile、完全SBOM、Release署名は後続EpochまたはTarget Setで閉じます。
