# 設計判断

## 日本語正本と英語識別子

説明、Skill、CLIの利用者向けメッセージは日本語を正本にします。Kotlin API、Schema Key、Capability ID、Pathは検索性と機械互換性のため英語を維持します。

## Automation Workbench

以前の設計で定義したAutomation Workbenchは破棄しません。ただし初回Epochで製品実装へ着手するとClaim/Evidence基盤よりDomain codeが先行するため、`reference-system.automation-workbench`を`planned`として保持します。

## 完成状態

Local Gateが通ってもContainer profileとInventory Closureが未完了なので、Repository statusは`incomplete`を維持します。
