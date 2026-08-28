# Definitive Gate v2 状況

## 判定

- Manifest status: `incomplete`
- v0.2.0 Certificate: `bounded-complete`の履歴証明
- Subject Definitive: 未完
- Completion Certificateの再発行: 禁止

v0.2.0は固定した28 Target、8 Source、Local／Container profileに対するCore v1証明として改変しません。一方、Native executable／Swift consumerの実Runtimeを`infeasible`、Automation Workbenchを`planned`として許容したため、Kotlin分野全体を閉じた証明には使用しません。現行候補はbaseline 8 Sourceと追加10 Source、9 Authority Artifact、69 Behavior、30 Gapを扱い、旧Certificateとは別の未完graphです。

## v2で追加した実体

`reference-systems/automation-workbench`は、複数の既存Surfaceを一つのWorkflowへ統合します。

- 正常実行と決定論的Artifact
- 入力境界、Strict拒否とNormalize Variant
- transient failureのbounded retryと回復
- permanent failureの分類とhealth観測
- CoroutineNameによるcontext伝播
- cancellationを業務失敗へ変換しないcleanup
- bounded Channelのbackpressureとclose後拒否
- Workflow IDによる重複実行の冪等化

JVM実Runtime Test 8件と集約Claim／Artifact Evidenceは接続済みです。実行時traceは正常、境界、拒否、障害、回復の8行を保存し、Strict／Normalize、bounded retry、idempotent replay、bounded Channel、cancellationの観測結果を含みます。ただし、5 Behaviorそれぞれの専用Claim／10 Scenario Proof、JS／Wasm／Native実Runtime、全Outcome／SurfaceのDefinitive Skill Evalへ未接続のため`partial`です。

## Kotlin Depth Parity

[`atlas/definitive/kotlin-depth-parity.json`](../atlas/definitive/kotlin-depth-parity.json)は、`frontend-behavior-atlas` commit `4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45`の`FE_DEPTH_REFERENCE.json`、参照文書、4 fixture、非後退baselineをdigest固定しています。Authority本文消化、Atomic behavior、実Runtime、Normal／Boundary／Refusal／Failure／Recovery／Migration／Operations／Security／Performance／Compatibility、Artifact・Trace、統合Reference System、Skill Eval、Rights／Provenance、非後退の18軸をKotlin固有denominatorへ写像します。

FE側の判定は1軸satisfied、17軸partialで`incomplete`です。KotlinはFEのTarget／Test／Capture等の絶対件数や比率を閾値にせず、69 Authority由来Behaviorと適用Scenario／Runtime／Profileを母集団にします。現在のKotlin判定も1軸satisfied、17軸partial、30件の軸別Gap参照です。`scripts/verify_fe_parity.py`は18軸ID、正本commitとdigest、Kotlin denominator、Behavior×Scenario×Profile×Proof×専用Artifact粒度、Evidence、Gap、非後退を検証し、Gapがある状態での`complete`またはCertificate発行を拒否します。

Authority locator抽出の方法論は`frontend-behavior-atlas` commit `cabf687bab769b17928d950acc416f3f77eb4ca3`へ別途digest固定しています。`authority/locator-extraction.json`は第三者本文を保存せず、URL、Source metadata、digest、locator offsetだけを許可します。現状は69件の既存reference edge分類に対し、本文全体の抽出候補0、Source body評価deferred 9、stale 0、Human review 0です。`scripts/verify_authority_locators.py`は本文field混入を拒否し、この未完状態を再集計します。本文全体のSurface denominatorが閉じるまで`authority-body-digestion`は`partial`です。

## Completion禁止条件

[`atlas/definitive/gap-ledger.yaml`](../atlas/definitive/gap-ledger.yaml)のrequired Gapがすべて`closed`になり、Core Definitive Gate v2が次を機械検証するまで`complete`へ戻しません。

- Authority由来Surfaceが全件分類されている。
- 各Behaviorに専用ClaimとProof Obligationがある。
- 適用Behaviorに正常、境界、拒否、障害、回復の専用Artifact Evidenceがある。
- Runtimeを要するProofは実Runtimeで実行され、compile／KLIBだけでは代替されない。
- 比較Surfaceに2件以上の実行Variantがある。
- 統合Reference Systemと全Outcome／SurfaceをDefinitive Skill Evalが辿れる。
- Native／Swift／Cを含むPlatform固有Runtimeが実行される。

## 非後退条件

公開main `e42f23d`をBaselineとして、28 Target、25 Claim、27 Proof、24 Evidence、8 Source、18 Skill Eval、34実行Test case、56 Assertion、JVM／JS／Wasm／Native compile task、macOS／Ubuntu CIを維持します。`scripts/verify_non_regression.py`が削除、格下げ、skip、Scope外退避、Evidence command置換を検出した場合、Definitive作業は未完のまま失敗します。

## 既知の外部条件

現在のLocal hostはCommand Line ToolsのみでFull Xcodeがありません。これはDefinitive未完の理由であり、免除ではありません。Full Xcodeを持つmacOS arm64実行環境でNative executable、C interop、Swift consumer、memory／debug証跡を取得する必要があります。
