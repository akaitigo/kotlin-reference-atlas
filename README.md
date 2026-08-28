# Kotlin 技術実証アトラス

`kotlin-reference-atlas` は、Kotlinの言語Semanticsと型、Coroutine/Flow、JVM/Native/JS/Wasm、Interop、Compiler/Runtime、Gradle/Toolchain、Testing、Performance、Security、Failure/Debugging、Compatibility/Migration、Operationsに関する技術的主張を、固定した一次資料と再実行可能なEvidenceへ接続するRepositoryです。

Coverage Epochは `2026-08-28`、対象製品VersionはKotlin `2.4.10`、Gradle `9.5.0`、kotlinx.coroutines `1.11.0`です。実行対象はJVM、Node.js上のKotlin/JSとKotlin/Wasm、macOS arm64向けNative KLIB、Java consumer境界です。

## 検証

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
PATH="$PWD/bin:$PATH" atlas audit . --gate definitive # 現在は非0終了が正しい
python3 scripts/verify.py
```

`bin/atlas` は `core.version.yaml` に固定した `reference-atlas-core` のcommitを検証してからCore CLIを実行します。既定では隣接Directory `../reference-atlas-core` を使用し、別配置では `ATLAS_CORE_DIR` を指定します。

## 状態

v0.2.0のCompletion Certificateは、28 Target／8 Sourceに対するCore v1の`bounded-complete`履歴として保存しています。現行Epochではbaseline 8 Sourceを不変に保った上で10 Sourceを追加固定し、9 Authority Artifactから69件の既存reference edgeを分類しました。さらに9 Kotlin Authority Sourceを7 unique Git documentへ正規化し、固定tree selectorから146146 raw anchor候補を本文非保存で列挙しています。候補は全件`pending-human`であり、Semantic Surface・Atomic behavior・Depth達成へは算入しません。現在は`status: incomplete`で、30 Gap（partial 14、open 13、blocked 3）を維持しています。Automation WorkbenchのJVM統合実装と8 Runtime Testは`partial`であり、KLIB compileはNative runtimeの代替に数えません。

Definitive移行状況は[`docs/DEFINITIVE_STATUS.md`](docs/DEFINITIVE_STATUS.md)、未Closureは[`atlas/definitive/gap-ledger.yaml`](atlas/definitive/gap-ledger.yaml)を正本として確認してください。`kotlin-depth-parity`はFE Depth Reference正本の18軸をKotlin固有denominatorへ写像し、現在は1軸satisfied、17軸partial、30件の軸別Gap参照があります。すべてが0になりCore v2 Gateが成功するまでは`complete`へ変更しません。

公開mainの非後退条件は[`docs/NON_REGRESSION_BASELINE.md`](docs/NON_REGRESSION_BASELINE.md)に固定しています。`scripts/verify.py`はDefinitive未完を確認する前に、既存Test／Proof／Platform／Source／Skill Eval／CIが縮小していないことを検証します。

## 正本

- Manifest：`atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`
- Capability／Claim：`atlas/`
- Authority／Gap：`authority/surfaces/`、`surface.inventory.yaml`、`atlas/definitive/gap-ledger.yaml`
- 実行証拠：`labs/`、`reference-systems/automation-workbench/`、`scripts/verify.py`、`evidence/`
- Agent Router：`.agents/skills/kotlin-reference-router/SKILL.md`
- 移行対応：`migrations/core-v1.yaml`、`migrations/definitive-v2.yaml`、`migrations/public-main-baseline-v1.json`

利用者向け文書は日本語、Schema Key・ID・Path・API名は英語を正本とします。
