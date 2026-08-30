# 統合Reference System

`apps/reference-system`は、個別Labの一覧では観測しにくいCross-behavior境界を一つのApplicationで実行するためのbounded Reference Systemです。対象は現行Frontend Domainだけで、Authority由来Atomic behaviorの完成や外部Profileの証明には使いません。

## 実行契約

```bash
pnpm reference:test
pnpm reference:verify
pnpm scenario:generate
pnpm scenario:verify
pnpm scenario:test
```

`reference:test`はproduction buildをCSP／Permissions Policy付きpreview serverで配信し、Chromiumを1 worker、retry 0、Trace常時有効で起動します。console errorとpage errorも失敗条件です。normal、boundary、refusal、failure、recovery、migration、operations、security、performance、compatibilityを個別Testとして実行し、次を保存します。

- `artifacts/reference-system/results.json`: Source／Harness digest、Node／OS／Architecture、Playwright／Browser version、Attempt、結果。
- `artifacts/reference-system/traces/*.trace.zip`: ScenarioごとのAction／Network／Resource stream。
- `artifacts/reference-system/screenshots/*.png`: 最終Observable state。

Manifestは`integrations/reference-system/manifest.json`です。各Scenarioは2件以上の既存Pattern、Runtime boundary、反証可能なAssertionへ接続します。

## Runtime boundary

- module Worker: 正常処理、強制失敗、新generationでの復旧、sample上限。
- bounded queue: offline中の上限、超過時のquality degradation、replay once。
- localStorage schema: v1からv2への明示Mappingと選択状態の連続性。
- CSP／Permissions Policy: Capabilityを要求せずrefusalを表示し、実Response headerを検証。
- DOM text sink: 未信頼入力をmarkupとして解釈しない。
- Resource ownership: Worker、timer、event listenerの所有数を観測し、operationsで0へ戻す。

## Pattern × Scenario Artifact

`scenario:generate`は現行85 Pattern × 10 Scenarioの850 JSONを`evidence/scenarios/patterns/`へ生成し、`evidence/scenarios/index.json`へdigest付きで列挙します。各rowは次の証拠を混同せずに保持します。

1. Variant Source pathとdigest。
2. Pattern固有のCapture、Benchmark、Compatibility record。
3. 同じScenarioの統合Reference System TraceとScreenshot。
4. Browser identity、Pattern mapping、Authority Human reviewの未達。

CaptureはSource／Harness／Image digestを持ちますが、現在のreportにBrowser versionがないため`real_runtime_identity`には数えません。PerformanceとCompatibilityは環境identityを持つ既存実Browser recordをPattern固有runtime proofとして接続します。統合TraceはCross-behaviorの境界証明で、直接MappingされていないPatternの固有proofへ昇格しません。

## 完了境界

850は現行Domainの非後退分母であり、Authority-derived denominatorではありません。全rowは`authority_atomic_behavior: false`と`completion_eligible: false`を維持します。Authority review、Pattern固有Scenario gap、Capture runtime identity、実Device／支援技術／Cloud／Hardware profileが未完了であるため、Reference Systemが10/10を通ってもRepository全体は`incomplete`です。
