# Kotlin Reference SystemとScenario Proof

`reference-systems/automation-workbench`は、Kotlin/JVM、Coroutine、入力境界、再試行、状態観測を一つの実行系で組み合わせる統合Reference Systemです。`normal`、`boundary`、`refusal`、`failure`、`recovery`、`migration`、`operations`、`security`、`performance`、`compatibility`の10 ScenarioをJUnitと実JVMで実行し、結果を`evidence/scenarios/integrated/`へScenario別Traceとして保持します。

統合Traceは統合境界の証拠であり、69件のAuthority inventory Behaviorを個別に証明するものではありません。Core互換の`evidence/scenarios/index.json`は69 Behavior×10 Scenarioの690行を保持し、Kotlin固有の`evidence/scenarios/kotlin-closure-index.json`は4590 Surface×Scenario×Variant cellへ展開します。各cellは専用実compiler/runtime/platformでVariantを駆動し、初回成功、retry 0、Source/Harness digest、Runtime identity、Oracle、Trace、Artifactが全て揃う場合だけcloseです。現在は4590 cellが全て`explicit-gap`です。

Authority Review Queueの人手decisionがAtomic behaviorへ結び付くまでは、統合Traceや既存Target Evidenceが成功していても`completion_eligible`は`false`です。統合System Traceと別Artifactのmetadataはcell固有Proofに流用しません。KLIB、bytecode、compile-only、static artifactは、実Runtimeが必要な行の代替にはしません。

`evidence/scenarios/closure-plan.json`は690 Gapをrisk順の180 trancheへ固定し、各行の全Variant、専用Runtime identity、Oracle、Action／Network／Resource trace、Source／Harness digestをClosure条件にします。実行Reporterは全Artifactを同一filesystem上のstaging directoryへ生成・検証し、full-run pass時だけdirectory renameで公開します。失敗runは直前の成功Evidenceを保持し、swap失敗時はbackupからrollbackします。部分上書き、新旧generation混在、失敗runによる成功Evidence消去はnegative testで拒否します。現状は公開可能な専用Runtime成功世代がないため、Core `evidence-durability`と、それを前提にする`scenario-plan`は明示的未完として非0終了します。

再生成と検証:

```console
./gradlew :reference-systems:automation-workbench:test :reference-systems:automation-workbench:captureRuntimeTrace --rerun-tasks --no-daemon
python3 scripts/capture_workbench.py
python3 scripts/generate_scenario_proofs.py
python3 scripts/verify_scenario_proofs.py
python3 scripts/generate_scenario_closure_plan.py
python3 scripts/verify_scenario_closure_plan.py
python3 scripts/test_atomic_evidence.py
```
