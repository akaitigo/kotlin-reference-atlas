# 設計判断

## 日本語正本と英語識別子

説明、Skill、CLIの利用者向けメッセージは日本語を正本にします。Kotlin API、Schema Key、Capability ID、Pathは検索性と機械互換性のため英語を維持します。

## Automation Workbench

以前の設計で定義したAutomation Workbenchは、Definitive v2再監査で統合Reference Systemとして実装を開始しました。`reference-systems/automation-workbench`はJVM上で正常、境界、拒否、障害、回復、backpressure、context、cancellation、Strict／Normalize比較を実行します。全Platform RuntimeとBehavior専用Evidence／Skill Evalへ未接続のため、状態は`partial`です。

## 完成状態

Local／Containerのbounded実装Gateが通っても、69 Behaviorの10 Scenario Matrix、Platform実Runtime、比較Variant、Definitive Skill Evalが未閉鎖なので、Repository statusは`incomplete`を維持します。
