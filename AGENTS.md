# Repository instructions

このRepositoryはKotlin 2.4.10を基準とする「Kotlin 技術実証アトラス」です。

## Canonical order

1. `mastery.yaml`で利用者OutcomeとSurfaceを確認する。
2. `sources.lock.yaml`でAuthorityを確認する。
3. `coverage.yaml`で対象Epochと状態を確認する。
4. `atlas/capabilities/`、`atlas/claims/`、`atlas/proof-obligations/`を読む。
5. 技術的主張には対応するLabとEvidenceを提示する。

## Boundaries

- Coverage外の機能を対応済みとして推測しない。
- 実行していない結果を`pass` Evidenceとして記録しない。
- `status: complete`への変更は全Required Profile、全Closure、Publication Gate、Completion Certificateが揃った場合だけ行う。
- 他Subject AtlasのSource TreeやDefault Branchへ依存しない。
- GitHub公開、Release、外部書き込みは明示的な依頼なしに行わない。

## Language and rights

- 利用者向け文書、Skill、CLIメッセージは日本語を正本とする。
- 英語の識別子と上流の正式名称は変更しない。
- 独自コードと独自文書はApache-2.0。第三者依存は`third_party/manifest.yaml`へ記録する。

## Validation

変更後は `PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml`、`PATH="$PWD/bin:$PATH" atlas audit .`、`python3 scripts/verify.py`を実行する。
