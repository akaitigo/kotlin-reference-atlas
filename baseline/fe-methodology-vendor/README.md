# FE方法論固定Snapshot

このdirectoryは、`frontend-behavior-atlas`の次のApache-2.0 Artifactをcommit単位で固定します。

- `7175de4`: 原子的Evidence公開・rollback検証
- `deadad18b6588d2c907170a451c3b5cea5ea4192`: Scenario Proof方法論
- `f2e4c4b19156f8e993f48cdcbce23679ad881924`: Scenario Gap Closure方法論

各Artifactの期待digestは`baseline/fe-atomic-evidence-reference-v1.json`、`baseline/fe-scenario-proof-reference-v1.json`、`baseline/fe-scenario-gap-closure-reference-v1.json`を正本とします。VerifierはSnapshot実体のdigestを検証し、byte mutationを拒否する負例も実行します。

これらはKotlin Runtime ProofやCompletion Authorityではなく、ReporterとVerifierの方法論固定にだけ使用します。実Kotlin EvidenceはRepository内のKotlin Source、Harness、Runtime identity、Artifact、Traceから別途生成します。
