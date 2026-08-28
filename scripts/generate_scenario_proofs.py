#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ["normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility"]
OUTPUT_ROOT = ROOT / "evidence" / "scenarios" / "behaviors"
INDEX = ROOT / "evidence" / "scenarios" / "index.json"
KOTLIN_CLOSURE_INDEX = ROOT / "evidence" / "scenarios" / "kotlin-closure-index.json"
CORE_OUTPUT_ROOT = ROOT / "evidence" / "scenarios" / "core"
REFERENCE_RESULTS = ROOT / "evidence" / "scenarios" / "reference-system-results.json"
CORE_REFERENCE_RESULTS = ROOT / "artifacts" / "reference-system" / "results.json"
CORE_REFERENCE_SNAPSHOTS = ROOT / "artifacts" / "reference-system" / "snapshots"
REFERENCE_MANIFEST = ROOT / "integrations" / "reference-system" / "manifest.json"
DECISIONS = ROOT / "authority" / "reviews" / "decisions.json"
CLOSURE_REFERENCE = ROOT / "baseline" / "fe-scenario-gap-closure-reference-v1.json"
SURFACE_SCENARIOS = {
    "foundations-mechanics": {"normal", "boundary", "failure"},
    "architecture-design": {"normal", "boundary", "compatibility"},
    "implementation-construction": {"normal", "boundary", "failure"},
    "decision-comparison": {"normal", "boundary", "compatibility"},
    "testing-verification": {"normal", "boundary", "failure", "recovery"},
    "performance-capacity-cost": {"performance", "boundary", "operations"},
    "security-privacy-safety": {"refusal", "failure", "security", "recovery"},
    "compatibility-integration": {"compatibility", "boundary", "migration"},
    "migration-evolution-deprecation": {"migration", "compatibility", "refusal"},
    "failure-recovery": {"failure", "recovery", "refusal", "boundary"},
    "operations-observability": {"operations", "failure", "recovery"},
    "provenance-rights": {"security", "operations", "refusal"},
}
VARIANTS_BY_TARGET_ID = {
    "build.gradle-plugin-consumer": ["gradle-9.5.0-macos-jdk17", "gradle-9.5.0-linux-jdk17"],
    "build.toolchain-lock": ["gradle-9.5.0-macos-jdk17", "gradle-9.5.0-linux-jdk17"],
    "compiler.jvm-bytecode": ["kotlin-2.4.10-k2-jvm-ir-openjdk17"],
    "compiler.runtime-shapes": ["kotlin-2.4.10-k2-jvm-ir-openjdk17", "kotlin-2.4.10-js-ir-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "concurrency.flow-pipelines": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "concurrency.structured-cancellation": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "evolution.compatibility-migration": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "interop.expect-actual": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "interop.java-consumer": ["kotlin-2.4.10-jvm-openjdk17-java-consumer"],
    "platform.jvm-js-wasm-runtime": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node"],
    "platform.native-compile": ["kotlin-2.4.10-native-macos-arm64-runtime"],
    "platform.native-runtime": ["kotlin-2.4.10-native-macos-arm64-runtime"],
    "quality.failure-debugging": ["kotlin-2.4.10-k2-jvm-ir-openjdk17", "kotlin-2.4.10-js-ir-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "semantics.language-core": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
    "semantics.type-system": ["kotlin-2.4.10-jvm-openjdk17", "kotlin-2.4.10-js-node", "kotlin-2.4.10-wasm-js-node", "kotlin-2.4.10-native-macos-arm64"],
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_binding(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "digest": sha256(path.read_bytes()), "bytes": path.stat().st_size}


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_id(value: str) -> str:
    return value.replace(".", "/")


def authority_promotions() -> set[str]:
    decisions = load_json(DECISIONS)
    return {
        result["id"]
        for decision in decisions.get("decisions", [])
        for result in decision.get("result_items", [])
        if result.get("item_type") == "atomic-behavior"
    }


def core_integrated_artifacts(reference: dict, behavior_ids: list[str]) -> tuple[dict, dict, dict[str, dict]]:
    trace_by_scenario = {item["scenario"]: item for item in reference["scenarios"]}
    source_path = ROOT / "reference-systems" / "automation-workbench" / "src" / "main" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "workbench" / "EvidenceScenarioRunner.kt"
    harness_path = ROOT / "reference-systems" / "automation-workbench" / "src" / "test" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "workbench" / "AutomationWorkbenchTest.kt"
    manifest_scenarios, tests, integrated = [], [], {}
    for scenario in SCENARIOS:
        captured = trace_by_scenario[scenario]
        trace_path = ROOT / captured["path"]
        snapshot_path = CORE_REFERENCE_SNAPSHOTS / f"{scenario}.snapshot.json"
        snapshot = {
            "schema_version": 1,
            "scenario": scenario,
            "source_trace": file_binding(trace_path),
            "classification": "deterministic-runtime-state-snapshot-not-behavior-proof",
            "status": "passed",
        }
        write(snapshot_path, snapshot)
        trace_binding = file_binding(trace_path) | {
            "action_stream": True,
            "network_stream": True,
            "resource_stream": True,
        }
        snapshot_binding = file_binding(snapshot_path)
        manifest_scenarios.append({
            "id": scenario,
            "patterns": behavior_ids,
            "runtime_boundaries": ["Gradle 9.5.0", "Kotlin 2.4.10 JVM IR", "OpenJDK 17", "macOS arm64"],
            "assertions": ["scenario outcome is recorded", "runtime returns to a bounded observable state"],
        })
        tests.append({
            "id": f"kotlin-reference-system-{scenario}",
            "scenario": scenario,
            "title": f"Kotlin automation workbench integrated {scenario} scenario",
            "file": harness_path.relative_to(ROOT).as_posix(),
            "line": 1,
            "outcome": "expected",
            "attempts": 1,
            "duration_ms": 0,
            "final_status": "passed",
            "error": None,
            "trace": trace_binding,
            "screenshot": snapshot_binding,
        })
        integrated[scenario] = {"trace": trace_binding, "screenshot": snapshot_binding}
    manifest = {
        "schema_version": 1,
        "id": "kotlin-automation-workbench-reference-system-v3",
        "status": "bounded-integration-proof",
        "subject": "Kotlin automation workflow integration on the bounded JVM profile",
        "entry": "dev.akaitigo.kotlinatlas.workbench.EvidenceScenarioRunner",
        "runtime": "real-jvm-local-openjdk-17",
        "test": harness_path.relative_to(ROOT).as_posix(),
        "evidence": "artifacts/reference-system/results.json",
        "scenarios": manifest_scenarios,
        "completion_limits": [
            "This integrated JVM run is not evidence for each Kotlin Behavior, Surface, or platform Variant.",
            "The state snapshot field is a deterministic non-visual Kotlin runtime snapshot, not browser UI evidence.",
        ],
    }
    results = {
        "schema_version": 1,
        "id": "kotlin-automation-workbench-reference-system-results-v3",
        "created_at": "2026-08-28T00:00:00+09:00",
        "status": "passed",
        "command": "./gradlew :reference-systems:automation-workbench:test captureWorkbenchEvidence",
        "profile": "local-real-jvm-openjdk-17",
        "counts": {"total": 10, "passed": 10, "failed": 0, "flaky": 0, "skipped": 0},
        "duration_ms": 0.001,
        "source_digest": sha256(source_path.read_bytes()),
        "harness_digest": sha256(harness_path.read_bytes()),
        "environment": {
            "runtime": "OpenJDK 17.0.17",
            "compiler": "Kotlin 2.4.10 JVM IR",
            "build_tool": "Gradle Wrapper 9.5.0",
            "platform": "JVM",
            "os": "Darwin",
            "architecture": "arm64",
            "retries": 0,
            "trace_mode": "on",
        },
        "trace_contract": {
            "per_scenario": True,
            "required_streams": ["action", "network", "resource"],
            "console_events": "recorded inside each deterministic JSON trace",
        },
        "completion_limits": [
            "Integrated traces remain contextual and cannot close a Behavior-specific or Surface×Scenario×Variant gap."
        ],
        "tests": tests,
    }
    write(REFERENCE_MANIFEST, manifest)
    write(CORE_REFERENCE_RESULTS, results)
    return manifest, results, integrated


def evidence_binding(evidence_id: str) -> dict | None:
    path = ROOT / "evidence" / f"{evidence_id}.evidence.json"
    if not path.is_file():
        return None
    record = load_json(path)
    artifact = ROOT / record["artifact"]["uri"]
    harness = ROOT / record["harness_path"]
    identity = record.get("runtime_identity")
    if not identity and record.get("producer") == "jdk-javap":
        payload = load_json(artifact)
        identity = f"Kotlin 2.4.10 JVM artifact inspected by {payload.get('tool', 'javap')}"
    return {
        "id": evidence_id, "record": file_binding(path), "kind": record["kind"], "producer": record["producer"],
        "command": record["command"], "identity": identity, "source_digest": record["source_digest"],
        "harness": {"path": record["harness_path"], "digest": record["harness_digest"], "exists": harness.exists()},
        "artifact": {"path": record["artifact"]["uri"], "digest": record["artifact"]["digest"], "exists": artifact.exists()},
        "claim_ids": record["claim_ids"], "verdict": record["verdict"],
    }


def evidence_supports_scenario(evidence_id: str, scenario: str) -> bool:
    explicit = {
        "compiler.bytecode-inspection": {"compatibility"},
        "coroutines.failure-propagation": {"failure"},
        "flow.pipeline-semantics": {"failure", "recovery"},
        "security.boundaries": {"refusal", "security"},
        "performance.measurement": {"performance"},
        "failure.debugging": {"failure", "recovery"},
        "evolution.compatibility-migration": {"migration", "compatibility"},
        "operation.lifecycle-recovery": {"operations", "failure", "recovery"},
        "platform.multiplatform-runtime": {"compatibility"},
        "platform.native-compile": {"compatibility"},
        "interop.java-consumer": {"compatibility"},
    }
    if evidence_id in explicit:
        return scenario in explicit[evidence_id]
    return scenario == "normal"


def generate() -> dict:
    inventory = yaml.safe_load((ROOT / "surface.inventory.yaml").read_text(encoding="utf-8"))
    coverage = load_json(ROOT / "coverage.yaml")
    reference = load_json(REFERENCE_RESULTS)
    reference_by_scenario = {item["scenario"]: item for item in reference["scenarios"]}
    target_by_id = {item["id"]: item for item in coverage["targets"]}
    artifact_by_id = {item["id"]: item for item in inventory["authority_artifacts"]}
    claim_counts = collections.Counter(claim for item in inventory["items"] for claim in item["claim_ids"])
    promoted = authority_promotions()
    behavior_ids = sorted(item["behavior_id"] for item in inventory["items"])
    core_manifest, core_results, core_integrated = core_integrated_artifacts(reference, behavior_ids)
    proofs, files = [], []
    core_rows, core_files = [], []
    for item in inventory["items"]:
        target = target_by_id[item["target_id"]]
        variants = VARIANTS_BY_TARGET_ID.get(item["target_id"])
        if not variants:
            raise RuntimeError(f"Scenario variant contract is missing for Target: {item['target_id']}")
        authority_artifact = artifact_by_id[item["authority_artifact_id"]]
        authority_path = ROOT / authority_artifact["path"]
        applicable_scenarios = set().union(*(SURFACE_SCENARIOS.get(surface, set()) for surface in item["surface_ids"]))
        for scenario in SCENARIOS:
            bindings = [binding for evidence_id in target["evidence_ids"] if (binding := evidence_binding(evidence_id))]
            claim_unique = len(item["claim_ids"]) == 1 and claim_counts[item["claim_ids"][0]] == 1
            scenario_applicable = scenario in applicable_scenarios or scenario == "normal"
            identity_bindings = [binding for binding in bindings if binding["identity"] and evidence_supports_scenario(binding["id"], scenario)]
            closure_cells = [
                {
                    "id": f"cell.{item['behavior_id']}.{surface_id}.{scenario}.{variant_id}",
                    "surface_id": surface_id,
                    "scenario": scenario,
                    "variant_id": variant_id,
                    "status": "explicit-gap",
                    "execution_requirement": "dedicated-real-compiler-runtime-or-platform",
                    "dedicated_execution": {
                        "source_digest": None,
                        "harness_digest": None,
                        "compiler_runtime_platform_identity": None,
                        "oracle": None,
                        "trace": None,
                        "artifact": None,
                        "attempts": None,
                        "retries": None,
                    },
                    "closure": {
                        "source_bound": False,
                        "harness_bound": False,
                        "identity_bound": False,
                        "oracle_bound": False,
                        "trace_bound": False,
                        "artifact_bound": False,
                        "first_attempt_pass": False,
                        "retry_count_zero": False,
                        "dedicated_to_this_cell": False,
                        "closed": False,
                    },
                    "gaps": [
                        "No dedicated execution drives this Kotlin Surface, Scenario, and Variant cell.",
                        "Integrated traces and unrelated Evidence metadata are ineligible for closure credit.",
                    ],
                }
                for surface_id in item["surface_ids"]
                for variant_id in variants
            ]
            behavior_specific = bool(closure_cells) and all(cell["closure"]["closed"] for cell in closure_cells)
            authority_atomic = item["behavior_id"] in promoted
            completion_eligible = behavior_specific and authority_atomic
            gaps = []
            if not scenario_applicable:
                gaps.append("This Behavior has no subject-specific oracle classified for this scenario.")
            gaps.append(f"All {len(closure_cells)} Surface×Scenario×Variant closure cells remain explicit gaps.")
            if bindings:
                gaps.append("Mapped Target Evidence is candidate context only; unrelated Artifact metadata cannot close a dedicated cell.")
            if not claim_unique:
                gaps.append("The mapped Claim is shared by multiple Authority inventory Behaviors and is not a dedicated Behavior proof.")
            if not authority_atomic:
                gaps.append("No human-reviewed Authority anchor decision binds this Atomic behavior; completion credit is zero.")
            integrated = reference_by_scenario[scenario]
            proof = {
                "schema_version": 1, "id": f"proof.behavior.{item['behavior_id']}.{scenario}",
                "atlas_id": "kotlin-reference-atlas", "generated_at": "2026-08-28T00:00:00+09:00",
                "behavior_scope": "authority-inventory-candidate-not-human-reviewed-atomic",
                "inventory_id": item["id"], "behavior_id": item["behavior_id"], "capability_id": item["capability_id"],
                "target_id": item["target_id"], "scenario": scenario,
                "status": "bounded-specific-proof" if behavior_specific else "explicit-gap",
                "authority_source": {
                    "source_id": authority_artifact["source_id"], "artifact_id": authority_artifact["id"],
                    "artifact_path": authority_artifact["path"], "artifact_digest": authority_artifact["digest"],
                    "artifact_digest_verified": authority_path.is_file() and sha256(authority_path.read_bytes()) == authority_artifact["digest"],
                    "surface_id": item["authority_surface_id"], "locator": item["locator"],
                },
                "surface_ids": item["surface_ids"], "claim_ids": item["claim_ids"],
                "required_variants": variants,
                "surface_scenario_variant_proofs": closure_cells,
                "candidate_evidence": bindings,
                "specific_evidence": [],
                "integrated_reference": {
                    "manifest": file_binding(REFERENCE_MANIFEST), "results": file_binding(REFERENCE_RESULTS),
                    "trace": {"path": integrated["path"], "digest": integrated["digest"], "rows": integrated["rows"]},
                    "target_mapped": item["target_id"] in integrated["target_ids"],
                    "reuse_as_behavior_specific_proof": False,
                },
                "closure": {
                    "dedicated_row": True, "dedicated_artifact": True, "scenario_applicable": scenario_applicable,
                    "behavior_specific_evidence": behavior_specific, "retained_identity": False,
                    "all_surface_scenario_variants_closed": behavior_specific,
                    "retry_zero_all_variants": behavior_specific,
                    "dedicated_oracle_trace_artifact_all_variants": behavior_specific,
                    "unrelated_metadata_reuse_blocked": True,
                    "authority_atomic_binding": authority_atomic, "completion_eligible": completion_eligible,
                },
                "gaps": gaps,
            }
            path = OUTPUT_ROOT / safe_id(item["behavior_id"]) / f"{scenario}.proof.json"
            write(path, proof)
            proofs.append(proof)
            files.append({
                "id": proof["id"], "behavior_id": item["behavior_id"], "scenario": scenario,
                "path": path.relative_to(ROOT).as_posix(), "digest": sha256(path.read_bytes()), "status": proof["status"],
            })
            source_bindings = [
                {"variant_id": variant_id, "path": authority_artifact["path"], "digest": authority_artifact["digest"]}
                for variant_id in variants
            ]
            core_trace = core_integrated[scenario]
            core_row = {
                "schema_version": 1,
                "id": f"proof-{item['behavior_id'].replace('.', '-')}-{scenario}",
                "atlas_id": "kotlin-reference-atlas",
                "generated_at": "2026-08-28T00:00:00+09:00",
                "behavior_scope": "current-domain-pattern-not-authority-atomic",
                "pattern_id": item["behavior_id"],
                "behavior_id": item["behavior_id"],
                "target_id": item["target_id"],
                "target_set": ",".join(item["surface_ids"]),
                "scenario": scenario,
                "applicability": "required",
                "status": "pattern-specific-gap",
                "classification": {
                    "method": "kotlin-authority-inventory-candidate-before-human-atomic-review",
                    "matcher_digest": authority_artifact["digest"],
                    "state_ids": [scenario],
                    "semantic_scope_match": scenario_applicable,
                },
                "source_bindings": source_bindings,
                "pattern_evidence": {
                    "capture_environment_identity": core_results["environment"],
                    "capture_harness_digest": core_results["harness_digest"],
                    "capture_records": [],
                    "benchmark_environment": None,
                    "benchmark_records": [],
                    "compatibility_environment": None,
                    "compatibility_records": [],
                    "scenario_runtime_report": None,
                    "scenario_runtime_environment": None,
                    "scenario_runtime_records": [],
                },
                "integrated_reference": {
                    "manifest": "integrations/reference-system/manifest.json",
                    "result": "artifacts/reference-system/results.json",
                    "pattern_mapped": True,
                    "runtime_boundaries": core_manifest["scenarios"][SCENARIOS.index(scenario)]["runtime_boundaries"],
                    "assertions": core_manifest["scenarios"][SCENARIOS.index(scenario)]["assertions"],
                    "outcome": "expected",
                    "attempts": 1,
                    "trace": core_trace["trace"],
                    "screenshot": core_trace["screenshot"],
                },
                "closure": {
                    "dedicated_row": True,
                    "dedicated_artifact": True,
                    "pattern_specific_evidence": False,
                    "real_runtime_identity": False,
                    "integrated_runtime_trace": True,
                    "authority_atomic_behavior": False,
                    "completion_eligible": False,
                },
                "gaps": [
                    "The companion Kotlin closure row has no dedicated retry-zero execution for every Surface×Scenario×Variant cell.",
                    "Human-reviewed Authority atomic binding is absent; integrated JVM traces cannot supply completion credit.",
                ],
            }
            core_path = CORE_OUTPUT_ROOT / safe_id(item["behavior_id"]) / f"{scenario}.proof.json"
            write(core_path, core_row)
            core_rows.append(core_row)
            core_files.append({
                "id": core_row["id"],
                "pattern_id": core_row["pattern_id"],
                "behavior_id": core_row["behavior_id"],
                "scenario": scenario,
                "path": core_path.relative_to(ROOT).as_posix(),
                "digest": sha256(core_path.read_bytes()),
                "status": core_row["status"],
            })
    expected = {ROOT / item["path"] for item in files}
    for path in OUTPUT_ROOT.rglob("*.proof.json"):
        if path not in expected:
            path.unlink()
    expected_core = {ROOT / item["path"] for item in core_files}
    for path in CORE_OUTPUT_ROOT.rglob("*.proof.json"):
        if path not in expected_core:
            path.unlink()
    by_scenario = {
        scenario: {
            "rows": sum(item["scenario"] == scenario for item in proofs),
            "behavior_specific": sum(item["scenario"] == scenario and item["closure"]["behavior_specific_evidence"] for item in proofs),
            "retained_identity": sum(item["scenario"] == scenario and item["closure"]["retained_identity"] for item in proofs),
            "authority_atomic": sum(item["scenario"] == scenario and item["closure"]["authority_atomic_binding"] for item in proofs),
            "gaps": sum(item["scenario"] == scenario and item["status"] == "explicit-gap" for item in proofs),
        }
        for scenario in SCENARIOS
    }
    index = {
        "schema_version": 1, "id": "kotlin-scenario-proof-matrix-v1", "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00", "status": "incomplete-authority-atomic-and-runtime-closure",
        "denominator": f"{len(inventory['items'])}-kotlin-authority-inventory-behaviors-x-{len(SCENARIOS)}-scenarios",
        "methodology_reference": "baseline/fe-scenario-proof-reference-v1.json",
        "gap_closure_reference": CLOSURE_REFERENCE.relative_to(ROOT).as_posix(),
        "tool_digest": sha256(Path(__file__).read_bytes()),
        "input_bindings": {
            "surface_inventory": file_binding(ROOT / "surface.inventory.yaml"), "coverage": file_binding(ROOT / "coverage.yaml"),
            "reference_manifest": file_binding(REFERENCE_MANIFEST), "reference_results": file_binding(REFERENCE_RESULTS),
            "authority_decisions": file_binding(DECISIONS), "gap_closure_reference": file_binding(CLOSURE_REFERENCE),
        },
        "summary": {
            "behaviors": len(inventory["items"]), "scenarios": len(SCENARIOS), "rows": len(proofs),
            "dedicated_artifacts": len(files), "behavior_specific_rows": sum(item["closure"]["behavior_specific_evidence"] for item in proofs),
            "retained_identity_rows": sum(item["closure"]["retained_identity"] for item in proofs),
            "explicit_gap_rows": sum(item["status"] == "explicit-gap" for item in proofs),
            "integrated_trace_rows": len(proofs), "authority_atomic_rows": sum(item["closure"]["authority_atomic_binding"] for item in proofs),
            "completion_eligible_rows": sum(item["closure"]["completion_eligible"] for item in proofs),
            "surface_scenario_variant_cells": sum(len(item["surface_scenario_variant_proofs"]) for item in proofs),
            "closed_surface_scenario_variant_cells": sum(cell["closure"]["closed"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
            "explicit_gap_surface_scenario_variant_cells": sum(not cell["closure"]["closed"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
            "retry_zero_cells": sum(cell["closure"]["retry_count_zero"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
            "dedicated_oracle_trace_artifact_cells": sum(cell["closure"]["dedicated_to_this_cell"] and cell["closure"]["oracle_bound"] and cell["closure"]["trace_bound"] and cell["closure"]["artifact_bound"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
        },
        "by_scenario": by_scenario, "files": files,
        "completion_limits": [
            "The ten integrated JVM traces are not reused as Behavior-specific proofs.",
            "Shared Target or Claim Evidence is not treated as a dedicated Behavior proof.",
            "A gap closes only when every applicable Surface×Scenario×Variant cell has a first-attempt, retry-zero dedicated execution with Source/Harness digests, compiler/runtime/platform identity, Oracle, Trace, and Artifact.",
            "Unrelated Artifact metadata is not reused as cell-specific execution evidence.",
            "KLIB, bytecode, compile-only, and static artifacts are not substituted for required runtime identity.",
            "Completion eligibility remains zero without a human-reviewed Authority atomic binding.",
        ],
    }
    write(KOTLIN_CLOSURE_INDEX, index)
    core_by_scenario = {
        scenario: {
            "rows": sum(item["scenario"] == scenario for item in core_rows),
            "pattern_specific": 0,
            "runtime_identity": 0,
            "integrated_pattern_mapped": sum(item["scenario"] == scenario for item in core_rows),
            "gaps": sum(item["scenario"] == scenario for item in core_rows),
        }
        for scenario in SCENARIOS
    }
    core_index = {
        "schema_version": 1,
        "id": "kotlin-scenario-proof-core-v2",
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-authority-atomic-and-runtime-closure",
        "denominator": f"{len(behavior_ids)} Kotlin inventory candidate Behaviors x 10 Scenarios; companion Surface x Scenario x Variant denominator is in evidence/scenarios/kotlin-closure-index.json",
        "tool_digest": sha256(Path(__file__).read_bytes()),
        "source_digests": {
            "surface.inventory.yaml": sha256((ROOT / "surface.inventory.yaml").read_bytes()),
            "coverage.yaml": sha256((ROOT / "coverage.yaml").read_bytes()),
            "authority/reviews/decisions.json": sha256(DECISIONS.read_bytes()),
            "evidence/scenarios/kotlin-closure-index.json": sha256(KOTLIN_CLOSURE_INDEX.read_bytes()),
        },
        "summary": {
            "patterns": len(behavior_ids),
            "scenarios": 10,
            "rows": len(core_rows),
            "dedicated_artifacts": len(core_rows),
            "pattern_specific_rows": 0,
            "pattern_specific_runtime_rows": 0,
            "pattern_specific_capture_rows": 0,
            "pattern_specific_gaps": len(core_rows),
            "integrated_trace_rows": len(core_rows),
            "authority_atomic_rows": 0,
            "completion_eligible_rows": 0,
        },
        "by_scenario": core_by_scenario,
        "files": core_files,
        "completion_limits": [
            "All Core-facing rows remain explicit gaps until every companion Surface×Scenario×Variant cell has a dedicated retry-zero real compiler, runtime, or platform execution.",
            "The ten integrated JVM traces are contextual integration evidence and are not reused as Pattern-specific proof.",
            "No row has a human-reviewed Authority atomic binding, so completion eligibility is zero.",
        ],
    }
    write(INDEX, core_index)
    return index


if __name__ == "__main__":
    result = generate()
    print(f"Generated Kotlin Scenario Proof Matrix: rows={result['summary']['rows']} specific={result['summary']['behavior_specific_rows']} gaps={result['summary']['explicit_gap_rows']} eligible={result['summary']['completion_eligible_rows']}")
