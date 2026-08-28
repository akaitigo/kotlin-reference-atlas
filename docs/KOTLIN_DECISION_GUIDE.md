# Kotlin決定版Decision Guide

## 読み方

この文書はKotlin 2.4.10、Coverage Epoch 2026-08-28に固定する。結論だけをコピーせず、各節のLab、Claim、Evidenceを再実行して採用条件を確認する。Framework固有APIは対象外であり、Kotlin本体とToolchainの境界を扱う。

## 言語Semanticsと型

- `sealed`階層は閉じた状態集合を表し、`when`のexhaustivenessをCompilerへ検査させる。外部拡張が必要なPlugin境界では閉包が制約になる。
- Nullabilityは値の有無を型へ移すが、Platform typeやJava境界では保証が弱くなる。Interop consumer Testを併用する。
- `out`はProducer、`in`はConsumerの置換を許す。mutable APIで両方を同時に公開する場合はInvariantを既定とする。
- `Nothing`は値を返さない失敗分岐をgeneric resultへ安全に埋め込める。
- `reified`はinline関数だけでRuntime type tokenを利用できる。型消去後の型引数全体を復元するものではない。
- delegated propertyとSequenceは遅延評価を導入する。初期化回数、評価開始点、terminal operationをTestする。

実証先：`labs/semantics`、Claim `semantics.exhaustive-and-lazy`、`types.variance-nothing-reified`。

## CoroutineとFlow

- `coroutineScope`内の子失敗は兄弟をcancelし、親へ例外を伝播する。Cleanupは`finally`で保証する。
- `CancellationException`を通常のDomain errorへ変換しない。再throwまたはCoroutine machineryへ委ねる。
- Flowはcold streamであり、`retry`は同じ値の再送ではなくupstreamの再収集である。side effectは再実行可能性を考慮する。
- `StateFlow`は最新状態を保持する。Eventの全件配送保証とは別Contractである。
- Collector cancellationでupstream cleanupが走ることを必須Oracleとする。

実証先：`labs/coroutines`、`labs/flow`。

## JVM、JS、Wasm、Native

- JVMではvalue classがsource-level分離を提供する一方、genericまたは`Any`境界でboxingされる。
- JVM、JS、Wasmの移植性判断は同じ`commonTest`を各Runtimeで実行して行う。compile成功だけをRuntime互換と呼ばない。
- `expect`/`actual`はPlatform差を明示する。共通Domain modelをPlatform APIへ直接汚染しない。
- NativeはmacOS arm64 KLIB compileを実証済み。Executable linkとSwift consumerはFull Xcode不在のため本Epochでは`infeasible`であり、同等に実証したとは主張しない。

実証先：`labs/jvm`、`labs/multiplatform`、`evidence/artifacts/platform-validation.json`。

## Interop

- Java consumerから見えるAPIをJava sourceでTestする。Kotlin側Reflectionだけではoverload、checked exception、nullability annotationのconsumer体験を証明できない。
- `@JvmOverloads`はdefault引数をJava overloadへ展開するが、API数とbinary compatibility costを増やす。
- `@Throws`はJava signatureへ例外Contractを公開する。Kotlin内部例外を無制限に漏らさず境界で分類する。
- Platform `actual`は各RuntimeでLinkする。Swift Exportは別Targetとして未実証を維持する。

実証先：`labs/interop`、`labs/multiplatform`。

## CompilerとRuntime

- data classは`componentN`、`copy`、equality等を生成する。公開APIへ含めると生成Memberも互換性Surfaceになる。
- capturing lambdaはlexical valueをRuntime objectへ保持し得る。長寿命Callbackでは保持期間を確認する。
- suspend関数はContinuationを受けるJVM signatureへLoweringされる。Stack traceとDebugging時はSourceの見た目だけで判断しない。
- bytecode主張は`javap` ArtifactをOracleとし、Compiler更新時に差分を確認する。

実証先：`labs/compiler-runtime`、`scripts/inspect_bytecode.py`。

## GradleとToolchain

- Gradle Wrapper distributionとWrapper JARのSHA-256を固定する。
- 全ProjectでDependency Lockを有効にし、Artifactは`verification-metadata.xml`で検証する。
- Pluginは独立TestKit consumerへ適用し、Plugin IDとTask出力を実行する。
- Kotlin/JSとWasmはSystem Nodeを利用し、Kotlin PluginによるNode/Yarn自動取得を無効にする。npm lockはSBOMへ含める。

実証先：`labs/gradle-plugin`、`gradle/`、`kotlin-js-store/`。

## Testing

正常値だけでなく、次のOracleを持つ。

1. 拒否：危険URI、Path traversal、未知Schema version。
2. 失敗：子Coroutine例外、Flow cancellation。
3. 回復：Service lifecycleのDEGRADEDからREADY。
4. 互換性：Java consumer、v1/v2 migration、JVM/JS/Wasm共通Test。
5. 生成物：javap、KLIB、Wasm、SBOM、InventoryのDigest。

## Performance

このAtlasはmicrobenchmarkの絶対値や方式の優越を固定しない。Harnessが複数Sample、Median、checksumを生成することを固定する。性能比較には同一Host、JDK、warm-up、GC条件、input sizeを追加で固定し、別Epoch Evidenceとして扱う。

## Security

- URIはHTTPS、Host allowlist、User info不在を検証する。
- File操作はnormalize後に許可Root内であることを検査する。
- Secret byte列はString変換せず`MessageDigest.isEqual`を利用する。
- DependencyはLock、checksum、SPDX SBOMへ接続する。
- Security LabはRepository内の入力だけを標的とし、第三者環境へ通信しない。

## FailureとDebugging

Failureを`input`、`state`、`unexpected`へ分類し、messageとcause typeを保持する。CancellationはこのDomain分類に混ぜない。診断時はClaimのOracle、JUnit XML、javap、Container logの順に実測へ戻る。

## CompatibilityとMigration

Versioned inputは既知Versionだけを現行Modelへ変換し、未知Versionをsilent defaultしない。Kotlin、KGP、Gradle更新はAuthority LockとCoverage Epochを更新し、旧Evidenceを上書きせず新しいEvidence Setを生成する。

## Operations

- Local：`python3 scripts/verify.py`で全ArtifactとEvidenceを再生成する。
- Container：`scripts/container-verify.sh`でGradle 9.5/JDK 17 imageをbuildし、networkなしで再実行する。
- 状態機械：STARTING → READY → DEGRADED → READY → STOPPEDを許可し、不正遷移を拒否する。
- Native runtime：Full Xcode導入後に`linkDebugTestMacosArm64`と`macosArm64Test`を再評価する。

## Agent Skill

`.agents/skills/kotlin-reference-router`は、設計、実装、診断、移行、ReviewをCoverage TargetへRouteする。`covered`以外を実証済みとせず、Swift ExportやFramework全APIには`gap`を返す。評価は`evals/router-cases.json`のObservable Routeで判定する。
