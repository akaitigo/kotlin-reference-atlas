# Local verification runbook

## Setup

- JDK 17以上
- Python 3.11以上
- Git
- Node.js 25（Kotlin/JS・Wasm実行）
- Docker 29（Container profile）
- `reference-atlas-core` commit `1ea027babf3a8d6720ac617c56988e447695ba63`

## Execute

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
PATH="$PWD/bin:$PATH" atlas audit . --gate definitive # 未完中は非0終了
PATH="$PWD/bin:$PATH" atlas audit . --gate non-regression
python3 scripts/verify.py
```

## Verify

`scripts/verify.py`の終了Code 0、`verification-summary.json`の`verdict: implementation-pass-definitive-incomplete`、各bounded `*.evidence.json`の`verdict: pass`を確認します。基礎`atlas audit .`は`completion_class=incomplete`、Definitive auditは非0終了でなければなりません。

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
