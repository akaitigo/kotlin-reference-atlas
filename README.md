# Kotlin 技術実証アトラス

`kotlin-reference-atlas` は、Kotlinの仕様・実装・Build・並行処理・相互運用に関する技術的主張を、固定した一次資料と再実行可能なEvidenceへ接続するRepositoryです。

初回Coverage Epochは `2026-08-28`、対象製品VersionはKotlin `2.4.10`です。現時点の対象はKotlin/JVM、Gradle 9.5.0、kotlinx.coroutines 1.11.0、Java consumer境界です。Kotlin全体の最終構想は維持しますが、未検証領域を完成済みとは扱いません。

## 検証

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
python3 scripts/verify.py
```

`bin/atlas` は `core.version.yaml` に固定した `reference-atlas-core` のcommitを検証してからCore CLIを実行します。既定では隣接Directory `../reference-atlas-core` を使用し、別配置では `ATLAS_CORE_DIR` を指定します。

## 状態

`status: incomplete` です。Local profileのLabsとSkill Evalは実装しますが、Container profile、Kotlin公開Surface全Inventory、KMP／Native／JS／Wasm、完全なSBOM、署名済みCompletion Certificateは未完了です。

## 正本

- Manifest：`atlas.yaml`、`mastery.yaml`、`sources.lock.yaml`、`coverage.yaml`、`skill.package.yaml`
- Capability／Claim：`atlas/`
- 実行証拠：`labs/`、`scripts/verify.py`、`evidence/`
- Agent Router：`.agents/skills/kotlin-reference-router/SKILL.md`
- 移行対応：`migrations/core-v1.yaml`

利用者向け文書は日本語、Schema Key・ID・Path・API名は英語を正本とします。
