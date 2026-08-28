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

JVM実Runtime Test 8件と集約Claim／Artifact Evidenceは接続済みです。実行時traceは正常、境界、拒否、障害、回復の8行を保存し、Strict／Normalize、bounded retry、idempotent replay、bounded Channel、cancellationの観測結果を含みます。ただし、5 Behaviorそれぞれの専用Claim／10 Scenario Proof、JS／Wasm／Native実Runtimeが未接続のため`partial`です。

Kotlin RouterはFE commit `8a9e34a89a55cc53702032783c06ede7246a286f`の方式をdigest固定し、8 Outcome×14 Surfaceの112 cellをKotlin固有Target setへ評価します。90 cellはcovered Targetの実装file、Authority Source、Claim、Evidence record、Artifact digestへ束縛し、22 cellはOutcomeとSurfaceのTarget setが交差しない`mastery-routing-gap`として隠さず記録します。変更権限、人手Authority decision、stale relock、曖昧／未知Query、Native runtime stateもfail-closedで検査します。独立Agent Forward Evalを含めてRouter契約がpassしても、Target／Depth／Runtime closureまたはCompletion Certificateを意味しません。

## Kotlin Depth Parity

[`atlas/definitive/kotlin-depth-parity.json`](../atlas/definitive/kotlin-depth-parity.json)は、`frontend-behavior-atlas` commit `4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45`の`FE_DEPTH_REFERENCE.json`、参照文書、4 fixture、非後退baselineをdigest固定しています。Authority本文消化、Atomic behavior、実Runtime、Normal／Boundary／Refusal／Failure／Recovery／Migration／Operations／Security／Performance／Compatibility、Artifact・Trace、統合Reference System、Skill Eval、Rights／Provenance、非後退の18軸をKotlin固有denominatorへ写像します。

FE側の判定は1軸satisfied、17軸partialで`incomplete`です。KotlinはFEのTarget／Test／Capture等の絶対件数や比率を閾値にせず、69 Authority由来Behaviorと適用Scenario／Runtime／Profileを母集団にします。現在のKotlin判定も1軸satisfied、17軸partial、30件の軸別Gap参照です。`scripts/verify_fe_parity.py`は18軸ID、正本commitとdigest、Kotlin denominator、Behavior×Scenario×Profile×Proof×専用Artifact粒度、Evidence、Gap、非後退を検証し、Gapがある状態での`complete`またはCertificate発行を拒否します。

Authority locator抽出の方法論は`frontend-behavior-atlas` commit `cabf687bab769b17928d950acc416f3f77eb4ca3`へdigest固定し、Core v2は確定tip `7c9313cfb3e3149af455976228b44bbcb706bf40`の独立Authority Extraction・Scenario/Trace・Closure Plan Gateを使用します。`authority/locator-extraction.json`とCore用`authority/extraction.snapshot.json`は第三者本文を保存せず、URL、Source metadata、digest、locator metadataだけを許可します。既存69 reference edge分類とAuthority本文全体の網羅抽出は別判定です。

Authority denominator方式は`frontend-behavior-atlas` commit `841ec2fa399606a10305021a8bcd396713b8cee5`へ別途digest固定しています。Kotlinでは18 Source Lock entryを16 documentへ正規化し、固定Git treeの`document-root`／`tracked-blob`と配布Artifact rootから146393 candidate anchorを列挙しました。本文は取得・保存せず、stable ID、source/tool digest、locator、offset、stale境界を保持します。公開済み146146 IDは維持し、Core e822→d535およびd535→7c9313c更新はlocator単位の旧ID→新ID Mappingを固定しました。専用baselineはMappingなしの削除・置換を拒否します。

Human review Queue方式はFE commit `de2f016b8b44ea67afdb08c0552044807505984e`へdigest固定しています。146393 stable anchorは全件Queueへ割り当て、priority・cluster・batchはmachine proposalに限定しています。現状は全件`pending-human`、Human decision 0、Semantic昇格0、stale hold 0です。reviewer、時刻、理由、固定digest、locator、旧→新mapping、result、Promotion実体が一致しない昇格をVerifierが拒否し、stale documentはholdします。candidate anchorおよびQueue件数はSemantic Surface、Atomic behavior、18 Depth軸の達成へ算入しません。

Reference System／Scenario Proof方式はFE commit `deadad18b6588d2c907170a451c3b5cea5ea4192`へ、Gap Closure条件はFE commit `f2e4c4b19156f8e993f48cdcbce23679ad881924`へdigest固定しています。Automation Workbenchの10統合Scenario Traceと、69 Authority inventory Behavior×10 Scenarioの690専用Artifactを分離し、4590 Surface×Scenario×Variant cellを展開しました。統合Traceや別Artifact metadataは個別Closureへ流用しません。各cellは専用実compiler/runtime/platformで全Variantを駆動し、初回成功・retry 0・Source/Harness digest・Runtime identity・Oracle・Trace・Artifactが揃う場合だけ閉じます。現状はclosed cell 0、明示Gap 4590、Human-reviewed Authority atomic binding 0、Completion eligible 0です。

Scenario Closure Planは690 Gapを180 trancheへ固定し、完了0、次回trancheは`security-001`です。Evidence公開はFE commit `7175de4`の原子的保存契約へdigest固定し、stagingで全Artifactを生成・検証したfull-run passだけをdirectory renameで公開します。失敗runは直前成功Evidenceを保持し、swap失敗はrollbackします。部分上書き、新旧generation混在、失敗runによる成功Evidence消去はnegative testで拒否します。

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

Core v2標準の`non-regression.yaml`は、この公開main非後退を通過したDCO commit `c0e9b1c60768f606221f6a3ef0556052a8b5d0e9`を追加anchorとして固定します。Core生成baselineは29 Claim、31 Proof、28 Evidence、18 Source、21 Skill Eval、30 Targetを保持し、同一Harnessの変更には実Runtime ProofとMigration Evidenceを要求します。公開main baselineを置換するものではなく、二層を両方通します。

## 既知の外部条件

現在のLocal hostはCommand Line ToolsのみでFull Xcodeがありません。これはDefinitive未完の理由であり、免除ではありません。Full Xcodeを持つmacOS arm64実行環境でNative executable、C interop、Swift consumer、memory／debug証跡を取得する必要があります。
