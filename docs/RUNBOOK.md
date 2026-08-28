# Local verification runbook

## Setup

- JDK 17以上
- Python 3.11以上
- Git
- Node.js 25（Kotlin/JS・Wasm実行）
- Docker 29（Container profile）
- `reference-atlas-core` commit `d5c0a6ce757fd5f43af837edd26f55c7325b811e`

## Execute

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
python3 scripts/verify.py
```

## Verify

終了Code 0、`evidence/artifacts/verification-summary.json`の`verdict: pass`、各`*.evidence.json`の`verdict: pass`を確認します。`atlas audit .`は`open_required=0`でなければなりません。

個別再実行：

```bash
./gradlew atlasCheck --no-daemon
python3 scripts/inventory.py
python3 scripts/inspect_bytecode.py
python3 scripts/generate_sbom.py
scripts/container-verify.sh
```

## Cleanup

```bash
./gradlew clean
```

Repository外のProcess、Credential、Cloud Assetは作成しません。Container image `kotlin-reference-atlas-verify:local`、Gradle cache、生成Evidenceは再検証と差分確認のため残します。
