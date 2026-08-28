# Mastery Contract v1移行記録

## 適用した契約

`reference-atlas-core` commit `d5c0a6ce757fd5f43af837edd26f55c7325b811e`の`docs/MIGRATION_MASTERY_V1.md`とSubject Delivery Strategyを適用した。

## 方針

- Kotlin以外の分野、製品、FrameworkをCoverageへ追加しない。
- 既存7 Target Set、12 Coverage Target、4 Labs、8 Evidence、Router Skillを維持する。
- 8 Outcomeと14 Surfaceを既存Target Setへ接続し、「Kotlinならここを見ればよい」ための不足を明示する。
- `mastery.yaml`は既存Manifestの代替ではなく、利用者が達成できるOutcomeと答えるべきSurfaceの正本とする。
- CycloneDX直接依存SBOMを維持し、新しいPublication Contract用にRootの`sbom.spdx.json`を追加する。

## 完了状態

Mastery移行と`atlas audit`が通っても、Container Evidence、完全な公開Surface Inventory、完全なtransitive SBOM、Completion Certificateが未完了なので`status: incomplete`を維持する。
