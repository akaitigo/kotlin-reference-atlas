---
name: kotlin-reference-router
description: Kotlinの設計、実装、診断、移行、レビューを、Kotlin 技術実証アトラスのCoverage、一次資料、再実行可能なLab、Evidenceへ案内する。言語Semantics、型、JVM/JS/Wasm/Native、Coroutine/Flow、Interop、Compiler、Gradle、Testing、Performance、Security、Operationsの検証済み判断に使い、一般的な他言語質問やCoverage外機能の断定には使わない。
---

# Kotlin Reference Router

Kotlinに関する依頼をAtlasの検証済みCapabilityへ接続する。技術知識をこのSkill内で複製せず、Canonical ManifestとEvidenceを優先する。

## Route

1. 依頼を`design`、`implement`、`diagnose`、`migrate`、`review`のいずれかとして捉える。境界は[references/modes.md](references/modes.md)を必要時だけ読む。
2. `mastery.yaml`のOutcomeとSurfaceを入口にし、`python3 scripts/route.py --query "<依頼の要約>"`を実行する。
3. `disposition: covered`なら、返されたOutcome、Surface、Capability、Lab、Claim、Evidenceを確認して回答または作業する。実行可能な依頼ではEvidenceに記録されたCommandを再実行する。
4. `disposition: gap`なら、未検証領域として明示し、存在しないCapabilityやEvidenceを捏造しない。`infeasible` Targetでは代替Evidenceと再評価条件を示す。

## Invariants

- 「Kotlinならここを見ればよい」の問いの範囲は`mastery.yaml`、検証状態は`coverage.yaml`に従う。
- Authorityの優先順位は`sources.lock.yaml`に従う。
- 技術的主張は`atlas/claims/claims.json`と`evidence/*.evidence.json`へ戻す。
- `verdict: conditional`、`boundary-only`、`planned`を`default`として扱わない。
- Evidenceを再実行していない場合は、固定Epochで記録済みの結果であることを明示する。
- 変更、公開、外部書き込みは依頼された範囲に限定する。GitHub公開を自動で行わない。
- Coverage外のKotlin機能を一般知識で説明することはできるが、Atlasが実証済みとは表現しない。
