#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "atlas" / "definitive" / "kotlin-depth-parity.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "kotlin-depth-parity.json"
REFERENCE_COMMIT = "4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45"
REFERENCE_DIGEST = "sha256:2452696f9807b7d4a8ffb22b3ba37f079a25a34ac2370d78423445b96064582a"
REFERENCE_ARTIFACTS = {
    "FE_DEPTH_REFERENCE.json": REFERENCE_DIGEST,
    "docs/DEFINITIVE_GATE_V2_REFERENCE.md": "sha256:280a398ed1251438ad244e999c9c9cef9b0b6b78217db82e2b55ef882306d241",
    "fixtures/definitive-gate-v2/authority-surface-inventory.fixture.json": "sha256:01c29cdd29f61968b06791edf3d0d0674462d279422bd312d523ab7964e2a1e4",
    "fixtures/definitive-gate-v2/variant-comparison.fixture.json": "sha256:2964d596201033761c083d06dc705d21a428de043a91a0f1e71e7d5b841f59d3",
    "fixtures/definitive-gate-v2/profile-incompatibility.fixture.json": "sha256:95c07992da4b78db5c5551d7ed0c4425668dde9188c0acb53c3b76b17a91e364",
    "fixtures/definitive-gate-v2/evidence-granularity.fixture.json": "sha256:94506646f1e30429cb84a87927e1af7e1e890d401efd0335ebf911aed6f85126",
    "baselines/definitive-gate-v2.json": "sha256:b6685fac1e11429ed7c203e35aac55c7a82c276dc32aadb97f225af801c3bb67",
    "artifacts/non-regression-report.json": "sha256:ea14a6b00c827c21fd90dbef23d6fd1e85cf81e4e8a65697a507af97d371bc66",
}
EXPECTED_AXES = {
    "authority-body-digestion", "surface-atomic-behavior-variant", "real-runtime-lab",
    "scenario-normal", "scenario-boundary", "scenario-refusal", "scenario-failure",
    "scenario-recovery", "scenario-migration", "scenario-operations", "scenario-security",
    "scenario-performance", "scenario-compatibility", "artifact-trace",
    "integrated-reference-system", "skill-eval", "rights-provenance", "non-regression-gate",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def yaml_values(path: Path, key: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(key)}:\s*(\S+)\s*$")
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values.append(match.group(1))
    return values


def verify_local_reference(expected: dict[str, str], errors: list[str]) -> dict:
    repository = ROOT.parent / "frontend-behavior-atlas"
    if not repository.exists():
        return {"available": False, "verified": False}
    kind = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-t", REFERENCE_COMMIT],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if kind.returncode != 0 or kind.stdout.strip() != b"commit":
        errors.append("Local FE Depth Reference commitを解決できない")
        return {"available": True, "verified": False}
    mismatches = []
    for artifact_path, expected_digest in sorted(expected.items()):
        completed = subprocess.run(
            ["git", "-C", str(repository), "show", f"{REFERENCE_COMMIT}:{artifact_path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        actual = "sha256:" + hashlib.sha256(completed.stdout).hexdigest() if completed.returncode == 0 else None
        if actual != expected_digest:
            mismatches.append(artifact_path)
    if mismatches:
        errors.append(f"Local FE Depth Reference artifact digest不一致: {mismatches}")
    return {"available": True, "verified": not mismatches, "artifact_count": len(expected)}


def main() -> None:
    matrix = load(MATRIX)
    reference = load(ROOT / matrix["depth_reference"])
    behaviors = set(yaml_values(ROOT / "surface.inventory.yaml", "behavior_id"))
    gaps = set(yaml_values(ROOT / "atlas" / "definitive" / "gap-ledger.yaml", "- id"))
    evidence = {
        item["id"]: item
        for path in (ROOT / "evidence").glob("*.evidence.json")
        for item in [load(path)]
    }
    errors: list[str] = []
    assigned: set[str] = set()
    axis_results = []

    if matrix.get("id") != "kotlin-depth-parity":
        errors.append("Kotlin Depth Parity IDが不一致")
    if reference.get("git_commit") != REFERENCE_COMMIT or matrix.get("reference_commit") != REFERENCE_COMMIT:
        errors.append("FE Depth Reference commitが固定値と一致しない")
    if reference.get("artifacts") != REFERENCE_ARTIFACTS:
        errors.append("FE Depth Referenceの文書・4 fixture・baseline固定digestが不一致")
    if reference.get("frontend_status") != "incomplete" or reference.get("frontend_summary") != {"satisfied": 1, "partial": 17, "missing": 0}:
        errors.append("FE正本の1/18 satisfied・incomplete境界が不一致")
    if reference.get("denominator_policy", {}).get("transplant_absolute_counts") is not False:
        errors.append("FE絶対件数をKotlin denominatorへ転用している")
    if reference.get("classification") == "completion-authority":
        errors.append("FE Depth ReferenceをKotlin Completion Authorityに昇格している")
    reference_axes = {axis["id"]: axis for axis in reference.get("axes", [])}
    matrix_axis_ids = {axis["id"] for axis in matrix.get("axes", [])}
    if set(reference_axes) != EXPECTED_AXES or matrix_axis_ids != EXPECTED_AXES:
        errors.append("FE正本とKotlin mappingの18 Axis ID集合が一致しない")
    if matrix.get("proof_unit") != reference.get("proof_unit"):
        errors.append("Behavior×Scenario×Profile×Proof×ArtifactのProof粒度が不一致")
    if matrix.get("closure_proof_unit") != "one authority-derived atomic behavior × one mapped Surface × one required scenario × every applicable implementation/runtime/platform Variant × one first-attempt retry-zero falsifiable proof × dedicated Oracle/Trace/Artifact":
        errors.append("Surface×Scenario×全Variantの専用Closure Proof粒度が不一致")
    local_reference = verify_local_reference(REFERENCE_ARTIFACTS, errors)

    for axis in matrix["axes"]:
        selected = {
            behavior
            for behavior in behaviors
            if any(fnmatch.fnmatchcase(behavior, selector) for selector in axis["behavior_selectors"])
        }
        if not selected:
            errors.append(f"Depth AxisがKotlin Behaviorへ接続されていない: {axis['id']}")
        assigned.update(selected)
        if not axis.get("kotlin_denominator"):
            errors.append(f"Kotlin固有denominatorがない: {axis['id']}")
        if axis["id"] not in reference_axes:
            errors.append(f"FE正本にないAxis: {axis['id']}")
        if not axis.get("checks"):
            errors.append(f"Kotlin Proof checkがない: {axis['id']}")
        check_states = [check.get("status") for check in axis.get("checks", [])]
        if any(state not in {"pass", "gap"} for state in check_states):
            errors.append(f"Kotlin Proof check statusが不正: {axis['id']}")
        unknown_gaps = sorted(set(axis["gap_ids"]) - gaps)
        if unknown_gaps:
            errors.append(f"Depth Axisが未知Gapを参照: {axis['id']} {unknown_gaps}")
        if axis["gap_count"] != len(axis["gap_ids"]):
            errors.append(f"Depth Axis gap_count不整合: {axis['id']}")
        missing_evidence = sorted(
            evidence_id
            for evidence_id in axis["current_evidence_ids"]
            if evidence_id not in evidence or evidence[evidence_id].get("verdict") != "pass"
        )
        if missing_evidence:
            errors.append(f"Depth Axis current Evidence不整合: {axis['id']} {missing_evidence}")
        if axis["status"] == "satisfied":
            if axis["gap_ids"] or axis["gap_count"] != 0 or any(state != "pass" for state in check_states):
                errors.append(f"satisfied AxisにGapが残る: {axis['id']}")
            closed_dimensions = set(axis.get("closed_dimensions", []))
            if not set(axis["required_dimensions"]).issubset(closed_dimensions):
                errors.append(f"satisfied AxisのEvidence dimensionが不足: {axis['id']}")
        elif axis["status"] in {"partial", "missing"}:
            if axis["gap_count"] == 0 or "gap" not in check_states:
                errors.append(f"未充足AxisがGapを保持していない: {axis['id']}")
        else:
            errors.append(f"Depth Axis statusが不正: {axis['id']}")
        axis_results.append({
            "id": axis["id"],
            "status": axis["status"],
            "behavior_count": len(selected),
            "gap_count": axis["gap_count"],
        })

    unassigned = sorted(behaviors - assigned)
    if unassigned:
        errors.append(f"Depth Axis未割当Behavior: {unassigned}")
    total_gaps = sum(item["gap_count"] for item in axis_results)
    all_closed = len(axis_results) == 18 and all(item["status"] == "satisfied" and item["gap_count"] == 0 for item in axis_results)
    atlas = load(ROOT / "atlas.yaml")
    certificate = ROOT / "evidence" / "definitive-certificate.json"
    if not all_closed:
        if atlas["status"] != "incomplete":
            errors.append("Kotlin Depth Parity Gapが残るのにatlas.statusがincompleteではない")
        if certificate.exists():
            errors.append("Kotlin Depth Parity Gapが残るのにDefinitive Certificateが存在する")
    else:
        audit = subprocess.run(
            [str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "definitive"],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if audit.returncode != 0:
            errors.append("Kotlin Depth Parity gap 0だがCore Definitive Gate v2が失敗する")

    status_counts = {
        status: sum(1 for item in axis_results if item["status"] == status)
        for status in ("satisfied", "partial", "missing")
    }

    result = {
        "schema_version": 1,
        "id": "kotlin-depth-parity",
        "matrix": MATRIX.relative_to(ROOT).as_posix(),
        "depth_reference": matrix["depth_reference"],
        "reference_commit": REFERENCE_COMMIT,
        "reference_frontend_status": reference["frontend_status"],
        "reference_frontend_summary": reference["frontend_summary"],
        "local_reference": local_reference,
        "absolute_count_threshold_transplanted": False,
        "kotlin_authority_behaviors": len(behaviors),
        "axis_count": len(axis_results),
        "status_counts": status_counts,
        "axis_results": axis_results,
        "unassigned_behaviors": unassigned,
        "total_axis_gaps": total_gaps,
        "all_axes_closed": all_closed,
        "core_definitive_required": True,
        "violations": errors,
        "verdict": "pass" if all_closed and not errors else "incomplete" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Kotlin Depth Parity Gate不整合: " + "; ".join(errors))
    print(f"Kotlin Depth Parity Gate: verdict={result['verdict']} axes={len(axis_results)} gaps={total_gaps} behaviors={len(behaviors)}")


if __name__ == "__main__":
    main()
