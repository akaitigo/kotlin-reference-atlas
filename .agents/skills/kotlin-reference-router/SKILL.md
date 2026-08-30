---
name: kotlin-reference-router
description: Kotlinの設計、実装、診断、移行、レビューを、Kotlin 技術実証アトラスのCoverage、一次資料、再実行可能なLab、Evidenceへ案内する。言語Semantics、型、JVM/JS/Wasm/Native、Coroutine/Flow、Interop、Compiler、Gradle、Testing、Performance、Security、Operationsの検証済み判断に使い、一般的な他言語質問やCoverage外機能の断定には使わない。
---

# Kotlin Reference Router

Kotlinに関する依頼をAtlasの検証済みCapabilityへ接続する。技術知識をこのSkill内で複製せず、Canonical ManifestとEvidenceを優先する。

## Route

1. 依頼を`mastery.yaml`の8 Outcomeと14 Surfaceへ明示的に分類する。境界は[references/modes.md](references/modes.md)を必要時だけ読む。
2. `python3 scripts/route.py --query "<依頼の要約>" --outcome <outcome-id> --surface <surface-id>`を実行する。`build`、`operate`、`troubleshoot`、`evolve`、`delegate`で利用者が変更を明示した場合だけ`--authorized-change`を付ける。
3. `disposition: covered`なら、Target state、実装Variant、Authority Source、Claim、Evidence record、Artifact digestを確認する。実行可能な依頼ではEvidenceのCommandを再実行する。
4. `disposition: gap`なら`reason_code`と`stop_conditions`を保ったまま停止する。曖昧・未知Queryを推測で補完せず、`partial`または`infeasible` Targetをcoveredとして扱わない。

## Invariants

- 「Kotlinならここを見ればよい」の問いの範囲は`mastery.yaml`、検証状態は`coverage.yaml`に従う。
- Authorityの優先順位は`sources.lock.yaml`に従う。
- 技術的主張は`atlas/claims/claims.json`と`evidence/*.evidence.json`へ戻す。
- `verdict: conditional`、`boundary-only`、`planned`を`default`として扱わない。
- Evidenceを再実行していない場合は、固定Epochで記録済みの結果であることを明示する。
- 変更、公開、外部書き込みは依頼された範囲に限定する。GitHub公開を自動で行わない。
- 変更権限をQueryの語調から推測しない。`unauthorized-mutation`では変更せず、明示権限を求める。
- Authority raw anchorの意味判断・Semantic Surface昇格は人手Review専用であり、Agentが代行しない。
- stale Sourceはholdし、明示的な再固定手順と人手確認なしにdigestを更新しない。
- `ambiguous-query`、`unknown-query`、`mastery-routing-gap`はfail-closedとし、近いTargetへ自動的に寄せない。
- 112-cell MatrixのpassはRouter契約のpassに限られ、Target、Depth、Repositoryのcompletionを意味しない。
- Coverage外のKotlin機能を一般知識で説明することはできるが、Atlasが実証済みとは表現しない。
