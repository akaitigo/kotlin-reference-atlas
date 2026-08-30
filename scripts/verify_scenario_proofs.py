#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

from generate_scenario_proofs import CLOSURE_REFERENCE, KOTLIN_CLOSURE_INDEX, OUTPUT_ROOT, REFERENCE_RESULTS, ROOT, SCENARIOS, VARIANTS_BY_TARGET_ID, sha256

REFERENCE = ROOT / "baseline" / "fe-scenario-proof-reference-v1.json"
REPORT = ROOT / "evidence" / "artifacts" / "scenario-proof-validation.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_reference(errors: list[str]) -> dict:
    reference = load(REFERENCE)
    repository = ROOT.parent / "frontend-behavior-atlas"
    expected_commit = "deadad18b6588d2c907170a451c3b5cea5ea4192"
    if reference.get("git_commit") != expected_commit or reference.get("absolute_counts_transplanted") is not False:
        errors.append("FE Scenario Proof methodology identity/count policyが不正")
    mismatches = []
    for path, digest in reference.get("artifacts", {}).items():
        result = subprocess.run(["git", "-C", str(repository), "show", f"{expected_commit}:{path}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or sha256(result.stdout) != digest:
            mismatches.append(path)
    if mismatches:
        errors.append(f"FE Scenario Proof methodology digest不一致: {mismatches}")
    return {"commit": expected_commit, "artifacts": len(reference.get("artifacts", {})), "verified": not mismatches}


def verify_closure_reference(errors: list[str]) -> dict:
    reference = load(CLOSURE_REFERENCE)
    repository = ROOT.parent / "frontend-behavior-atlas"
    expected_commit = "f2e4c4b19156f8e993f48cdcbce23679ad881924"
    policy = reference.get("kotlin_mapping", {})
    required_true = {
        "first_attempt_only", "requires_dedicated_source_digest", "requires_dedicated_harness_digest",
        "requires_dedicated_compiler_runtime_platform_identity", "requires_dedicated_oracle",
        "requires_dedicated_trace", "requires_dedicated_artifact", "all_applicable_variants_required",
    }
    if reference.get("git_commit") != expected_commit or policy.get("proof_unit") != "behavior-surface-scenario-variant" or policy.get("retry_count") != 0:
        errors.append("FE Scenario gap closure methodology identity/policyが不正")
    if any(policy.get(field) is not True for field in required_true) or policy.get("integrated_trace_reuse_allowed") is not False or policy.get("unrelated_artifact_metadata_reuse_allowed") is not False:
        errors.append("Kotlin Scenario gap closureの専用実行条件が不足")
    mismatches = []
    for path, digest in reference.get("artifacts", {}).items():
        result = subprocess.run(["git", "-C", str(repository), "show", f"{expected_commit}:{path}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or sha256(result.stdout) != digest:
            mismatches.append(path)
    if mismatches:
        errors.append(f"FE Scenario gap closure methodology digest不一致: {mismatches}")
    return {"commit": expected_commit, "artifacts": len(reference.get("artifacts", {})), "verified": not mismatches}


def main() -> None:
    errors: list[str] = []
    index = load(KOTLIN_CLOSURE_INDEX)
    inventory = yaml.safe_load((ROOT / "surface.inventory.yaml").read_text(encoding="utf-8"))
    behaviors = {item["behavior_id"] for item in inventory["items"]}
    if index.get("schema_version") != 1 or index.get("id") != "kotlin-scenario-proof-matrix-v1" or index.get("status") != "incomplete-authority-atomic-and-runtime-closure":
        errors.append("Scenario Proof index identity/statusが不正")
    if index.get("tool_digest") != sha256((ROOT / "scripts" / "generate_scenario_proofs.py").read_bytes()):
        errors.append("Scenario Proof generator digestがdriftしている")
    expected_pairs = {(behavior, scenario) for behavior in behaviors for scenario in SCENARIOS}
    indexed_pairs = {(item["behavior_id"], item["scenario"]) for item in index.get("files", [])}
    if indexed_pairs != expected_pairs or len(index.get("files", [])) != len(expected_pairs):
        errors.append("Scenario Proof MatrixがBehavior×10 Scenarioの直積ではない")
    expected_files = {item["path"] for item in index.get("files", [])}
    actual_files = {path.relative_to(ROOT).as_posix() for path in OUTPUT_ROOT.rglob("*.proof.json")}
    if actual_files != expected_files:
        errors.append("Scenario Proof専用Artifact集合がIndexと一致しない")
    proofs = []
    partial_report_path = ROOT / "artifacts" / "scenario-partial-runtime" / "results.json"
    partial_report = load(partial_report_path)
    partial_records = {record["id"]: record for record in partial_report.get("records", [])}
    if partial_report.get("status") != "passed" or partial_report.get("execution", {}).get("retries") != 0:
        errors.append("security-001 partial Runtime reportがpass/retry 0ではない")
    used_dedicated_paths = set()
    reference_results = load(REFERENCE_RESULTS)
    trace_by_scenario = {item["scenario"]: item for item in reference_results["scenarios"]}
    for item in index.get("files", []):
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path.read_bytes()) != item["digest"]:
            errors.append(f"Scenario Proof digest不一致: {item['path']}")
            continue
        proof = load(path)
        proofs.append(proof)
        if (proof.get("id"), proof.get("behavior_id"), proof.get("scenario"), proof.get("status")) != (item["id"], item["behavior_id"], item["scenario"], item["status"]):
            errors.append(f"Scenario Proof identity不一致: {item['path']}")
        closure = proof.get("closure", {})
        if closure.get("dedicated_row") is not True or closure.get("dedicated_artifact") is not True:
            errors.append(f"Scenario Proof専用row/artifactが不足: {proof.get('id')}")
        if proof.get("integrated_reference", {}).get("reuse_as_behavior_specific_proof") is not False:
            errors.append(f"統合TraceをBehavior固有Proofへ流用: {proof.get('id')}")
        trace = trace_by_scenario.get(proof.get("scenario"), {})
        bound_trace = proof.get("integrated_reference", {}).get("trace", {})
        trace_path = ROOT / str(bound_trace.get("path", "missing"))
        if bound_trace.get("digest") != trace.get("digest") or not trace_path.is_file() or sha256(trace_path.read_bytes()) != trace.get("digest"):
            errors.append(f"Scenario integrated trace binding不一致: {proof.get('id')}")
        authority = proof.get("authority_source", {})
        authority_path = ROOT / str(authority.get("artifact_path", "missing"))
        if not authority_path.is_file() or sha256(authority_path.read_bytes()) != authority.get("artifact_digest") or authority.get("artifact_digest_verified") is not True:
            errors.append(f"Scenario Authority Source binding不一致: {proof.get('id')}")
        variants = proof.get("required_variants", [])
        expected_variants = VARIANTS_BY_TARGET_ID.get(proof.get("target_id"), [])
        if variants != expected_variants or not variants:
            errors.append(f"Scenario Variant denominator不一致: {proof.get('id')}")
        expected_cells = {
            (surface_id, proof.get("scenario"), variant_id)
            for surface_id in proof.get("surface_ids", [])
            for variant_id in expected_variants
        }
        cells = proof.get("surface_scenario_variant_proofs", [])
        actual_cells = {(cell.get("surface_id"), cell.get("scenario"), cell.get("variant_id")) for cell in cells}
        if actual_cells != expected_cells or len(cells) != len(expected_cells):
            errors.append(f"Surface×Scenario×Variant cell denominator不一致: {proof.get('id')}")
        closed_cells = []
        for cell in cells:
            cell_closure = cell.get("closure", {})
            dedicated = cell.get("dedicated_execution", {})
            required_flags = [
                "source_bound", "harness_bound", "identity_bound", "oracle_bound", "trace_bound",
                "artifact_bound", "first_attempt_pass", "retry_count_zero", "dedicated_to_this_cell",
            ]
            should_close = all(cell_closure.get(field) is True for field in required_flags)
            if cell_closure.get("closed") is not should_close:
                errors.append(f"Scenario cell closure flag不整合: {cell.get('id')}")
            if should_close:
                closed_cells.append(cell)
                report_record = partial_records.get(cell.get("id"))
                if not report_record or any(dedicated.get(field) != report_record.get(field) for field in (
                    "source_digest", "harness_digest", "compiler_runtime_platform_identity", "oracle",
                    "trace", "artifact", "attempts", "retries",
                )):
                    errors.append(f"Scenario cellが専用Runtime report実体と一致しない: {cell.get('id')}")
                if dedicated.get("attempts") != 1 or dedicated.get("retries") != 0:
                    errors.append(f"Scenario cellが初回成功/retry 0ではない: {cell.get('id')}")
                if not all(dedicated.get(field) for field in ("source_digest", "harness_digest", "compiler_runtime_platform_identity", "oracle", "trace", "artifact")):
                    errors.append(f"Scenario cell専用Identity/Oracle/Artifactが不足: {cell.get('id')}")
                for artifact_field in ("trace", "artifact"):
                    artifact = dedicated.get(artifact_field, {})
                    artifact_path = ROOT / str(artifact.get("path", "missing"))
                    if not artifact_path.is_file() or sha256(artifact_path.read_bytes()) != artifact.get("digest"):
                        errors.append(f"Scenario cell専用{artifact_field} binding不一致: {cell.get('id')}")
                    if artifact.get("path") in used_dedicated_paths:
                        errors.append(f"Scenario cell専用Artifact pathが別cellと共有されている: {artifact.get('path')}")
                    used_dedicated_paths.add(artifact.get("path"))
                trace_payload = load(ROOT / dedicated["trace"]["path"])
                if set(trace_payload.get("streams", {})) != {"action", "network", "resource"}:
                    errors.append(f"Scenario cell専用Trace streamが不足: {cell.get('id')}")
                if dedicated.get("trace", {}).get("path") == dedicated.get("artifact", {}).get("path"):
                    errors.append(f"Scenario cell Trace/Artifactが独立していない: {cell.get('id')}")
            elif not cell.get("gaps"):
                errors.append(f"Scenario cell gapが明示されていない: {cell.get('id')}")
        all_cells_closed = bool(cells) and len(closed_cells) == len(cells)
        if closure.get("all_surface_scenario_variants_closed") is not all_cells_closed or closure.get("behavior_specific_evidence") is not all_cells_closed:
            errors.append(f"Behavior closureが全Surface/Variant cellと一致しない: {proof.get('id')}")
        if closure.get("unrelated_metadata_reuse_blocked") is not True or proof.get("specific_evidence"):
            errors.append(f"別Artifact metadataをScenario closureへ流用: {proof.get('id')}")
        if not closure.get("behavior_specific_evidence") and not proof.get("gaps"):
            errors.append(f"Behavior固有Proofなしrowに明示Gapがない: {proof.get('id')}")
        if closure.get("completion_eligible") and not (closure.get("behavior_specific_evidence") and closure.get("authority_atomic_binding")):
            errors.append(f"Authority atomic bindingなしのCompletion credit: {proof.get('id')}")
    expected_summary = {
        "behaviors": len(behaviors), "scenarios": len(SCENARIOS), "rows": len(proofs), "dedicated_artifacts": len(proofs),
        "behavior_specific_rows": sum(item["closure"]["behavior_specific_evidence"] for item in proofs),
        "retained_identity_rows": sum(item["closure"]["retained_identity"] for item in proofs),
        "explicit_gap_rows": sum(item["status"] == "explicit-gap" for item in proofs),
        "integrated_trace_rows": len(proofs),
        "authority_atomic_rows": sum(item["closure"]["authority_atomic_binding"] for item in proofs),
        "completion_eligible_rows": sum(item["closure"]["completion_eligible"] for item in proofs),
        "surface_scenario_variant_cells": sum(len(item["surface_scenario_variant_proofs"]) for item in proofs),
        "closed_surface_scenario_variant_cells": sum(cell["closure"]["closed"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
        "explicit_gap_surface_scenario_variant_cells": sum(not cell["closure"]["closed"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
        "retry_zero_cells": sum(cell["closure"]["retry_count_zero"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
        "dedicated_oracle_trace_artifact_cells": sum(cell["closure"]["dedicated_to_this_cell"] and cell["closure"]["oracle_bound"] and cell["closure"]["trace_bound"] and cell["closure"]["artifact_bound"] for item in proofs for cell in item["surface_scenario_variant_proofs"]),
    }
    if index.get("summary") != expected_summary:
        errors.append("Scenario Proof summaryがArtifact実体と一致しない")
    if expected_summary["authority_atomic_rows"] != 0 or expected_summary["completion_eligible_rows"] != 0:
        errors.append("Human Authority review未完なのにCompletion eligibleが0ではない")
    methodology = verify_reference(errors)
    closure_methodology = verify_closure_reference(errors)
    report = {
        "schema_version": 1, "index": KOTLIN_CLOSURE_INDEX.relative_to(ROOT).as_posix(), "methodology": methodology, "closure_methodology": closure_methodology,
        "summary": expected_summary, "integrated_trace_reuse_blocked": True,
        "unrelated_artifact_metadata_reuse_blocked": True, "retry_zero_first_attempt_required": True,
        "authority_atomic_completion_blocked": True, "violations": errors, "verdict": "pass" if not errors else "fail",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Scenario Proof Gate失敗: " + "; ".join(errors[:20]))
    print(f"Scenario Proof Gate: rows={expected_summary['rows']} cells={expected_summary['surface_scenario_variant_cells']} closed-cells={expected_summary['closed_surface_scenario_variant_cells']} gap-cells={expected_summary['explicit_gap_surface_scenario_variant_cells']} authority-atomic=0 eligible=0")


if __name__ == "__main__":
    main()
