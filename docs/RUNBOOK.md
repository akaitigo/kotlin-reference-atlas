# Local verification runbook

## Setup

- JDK 17以上
- Python 3.11以上
- Git
- `reference-atlas-core` commit `d5c0a6ce757fd5f43af837edd26f55c7325b811e`

## Execute

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
python3 scripts/verify.py
```

## Verify

終了Code 0、`evidence/artifacts/verification-summary.json`の`verdict: pass`、各`*.evidence.json`の`verdict: pass`を確認します。

## Cleanup

```bash
./gradlew clean
```

Repository外のProcess、Credential、Cloud Assetは作成しません。Gradle cacheと生成Evidenceは明示的に残し、再検証と差分確認に利用します。
