# Contribution

変更は日本語の利用者向け正本と英語の識別子を維持し、Capability、Claim、Proof Obligation、Lab、Evidenceの接続を更新してください。

CommitにはDeveloper Certificate of Origin 1.1への同意を示す `Signed-off-by` trailerが必要です。

```bash
git commit --signoff
```

提出前に次を実行してください。

```bash
PATH="$PWD/bin:$PATH" atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml
PATH="$PWD/bin:$PATH" atlas audit .
python3 scripts/verify.py
```
