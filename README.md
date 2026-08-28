# Kotlin 技術実証アトラス

`kotlin-reference-atlas` は、Kotlinの言語Semanticsと型、Coroutine/Flow、JVM/Native/JS/Wasm、Interop、Compiler/Runtime、Gradle/Toolchain、Testing、Performance、Security、Failure/Debugging、Compatibility/Migration、Operationsに関する技術的主張を、固定した一次資料と再実行可能なEvidenceへ接続するRepositoryです。

Coverage Epochは `2026-08-28`、対象製品VersionはKotlin `2.4.10`、Gradle `9.5.0`、kotlinx.coroutines `1.11.0`です。実行対象はJVM、Node.js上のKotlin/JSとKotlin/Wasm、macOS arm64向けNative KLIB、Java consumer境界です。

## 検証

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
python3 scripts/verify.py
```

`bin/atlas` は `core.version.yaml` に固定した `reference-atlas-core` のcommitを検証してからCore CLIを実行します。既定では隣接Directory `../reference-atlas-core` を使用し、別配置では `ATLAS_CORE_DIR` を指定します。

## 状態

固定EpochのRequired Coverageは`covered`または再評価日付き`infeasible`で閉じ、Local/Container profile、Claim/Evidence Graph、Skill Eval、Maven/npm Supply-chain、Provenance、Completion Certificateの全Gateを通過したため`status: complete`です。Native executable実行はFull Xcode不在のため`infeasible`で、Native test KLIB compileを代替Evidenceとします。

## 正本

- Manifest：`atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`
- Capability／Claim：`atlas/`
- 実行証拠：`labs/`、`scripts/verify.py`、`scripts/inventory.py`、`scripts/inspect_bytecode.py`、`scripts/generate_sbom.py`、`evidence/`
- Agent Router：`.agents/skills/kotlin-reference-router/SKILL.md`
- 移行対応：`migrations/core-v1.yaml`

利用者向け文書は日本語、Schema Key・ID・Path・API名は英語を正本とします。
