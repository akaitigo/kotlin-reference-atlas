# Failure Catalog

| Failure | 検出 | 分離 | 回復 |
|---|---|---|---|
| 子Coroutine失敗 | `coroutines.failure-propagation` | Repository内Test scope | 兄弟`finally`完了後に親で分類する |
| Flow collector cancel | `flow.pipeline-semantics` | `runBlocking` Test scope | Cleanup完了を確認し再収集する |
| 危険URI | `security.boundaries` | 固定文字列fixture | HTTPSとHost allowlistを満たす入力へ修正する |
| Path traversal | `security.boundaries` | `build/sandbox`相対Path | 許可Root内の正規化Pathへ修正する |
| 未知Schema | `evolution.compatibility-migration` | Map fixture | 対応Migrationを追加するまで拒否する |
| Dependency drift | `build.toolchain-lock` | Gradle verification | Authority確認後にLockとchecksumを明示更新する |
| JS/Wasm Node不足 | Gradle task configuration | System Nodeのみ | `ATLAS_NODE`で固定Executableを指定する |
| Native link失敗 | `xcrun xcodebuild -version` | macOS Host | Full Xcode導入後に再評価する |
| Container差異 | `operation.container-verification` | Gradle 9.5/JDK17 image | Image digestとLockを確認して再buildする |

第三者環境へFailure Injectionを行わない。すべての失敗入力はRepository内fixtureまたはephemeral Containerへ限定する。
