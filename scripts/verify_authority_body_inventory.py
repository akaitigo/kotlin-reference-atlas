#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "authority" / "body-inventory.snapshot.json"
BASELINE = ROOT / "baselines" / "authority-body-inventory-v1.json"
MIGRATION = ROOT / "migrations" / "authority-body-inventory-v1.json"
REFERENCE = ROOT / "baseline" / "fe-authority-body-reference-v1.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "authority-body-inventory-validation.json"
FORBIDDEN_FIELDS = {"body", "body_text", "content", "excerpt", "heading", "html", "markdown", "quote", "raw_body", "response_body", "source_text", "text"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def anchor_id(document: str, commit: str, locator: str) -> str:
    value = f"{document}\0{commit}\0{locator}".encode()
    return "anchor-" + hashlib.sha256(value).hexdigest()[:20]


def reject_body_fields(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "_") in FORBIDDEN_FIELDS:
                errors.append(f"第三者本文fieldは禁止: {path}.{key}")
            reject_body_fields(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_body_fields(child, f"{path}[{index}]", errors)


def verify_reference(reference: dict, errors: list[str]) -> dict:
    repository = ROOT.parent / "frontend-behavior-atlas"
    if reference.get("git_commit") != "841ec2fa399606a10305021a8bcd396713b8cee5" or reference.get("classification") != "methodology-reference-not-completion-authority":
        errors.append("FE Authority body methodology identityが不正")
    if not repository.is_dir():
        return {"available": False, "verified": False}
    mismatches = []
    for path, expected in sorted(reference.get("artifacts", {}).items()):
        result = subprocess.run(["git", "-C", str(repository), "show", f"{reference['git_commit']}:{path}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or sha256(result.stdout) != expected:
            mismatches.append(path)
    if mismatches:
        errors.append(f"FE Authority body methodology digest不一致: {mismatches}")
    return {"available": True, "verified": not mismatches, "artifact_count": len(reference.get("artifacts", {}))}


def main() -> None:
    index, baseline, migration, reference = load(INDEX), load(BASELINE), load(MIGRATION), load(REFERENCE)
    errors: list[str] = []
    reject_body_fields(index, "authority.body-inventory", errors)
    tool_digest = sha256((ROOT / "scripts" / "capture_authority_body_inventory.py").read_bytes())
    if index.get("tool_digest") != tool_digest or baseline.get("tool_digest") != tool_digest:
        errors.append("Authority raw-anchor tool digestがdriftしている")
    if index.get("selector_contract") != ["repository-root", "tracked-blob"] or baseline.get("selector_contract") != index.get("selector_contract"):
        errors.append("Authority raw-anchor selector contractがdriftしている")
    if index.get("denominator_policy") != "raw-anchor-candidates-not-semantic-surface-or-depth-credit":
        errors.append("Raw anchor件数をSemantic Surface/Depthへ算入している")
    if index.get("status") != "incomplete-human-review-required" or index.get("body_storage") != "digest-locator-and-metadata-only":
        errors.append("Authority raw-anchor未完または本文保存境界が不正")
    depth = load(ROOT / "atlas" / "definitive" / "kotlin-depth-parity.json")
    if depth.get("raw_anchor_policy") != "candidate-count-excluded-from-semantic-surface-and-depth-credit":
        errors.append("Kotlin Depth mappingがraw anchor非算入を固定していない")

    baseline_by_id = {item["id"]: item for item in baseline.get("documents", [])}
    index_by_id = {item["id"]: item for item in index.get("documents", [])}
    if len(baseline_by_id) != len(baseline.get("documents", [])) or set(baseline_by_id) != set(index_by_id):
        errors.append("Authority document baseline集合が削除・重複している")
    all_ids: set[str] = set()
    anchors = 0
    source_entries = 0
    for record in index.get("documents", []):
        path = ROOT / record["path"]
        if not path.is_file() or sha256(path.read_bytes()) != record.get("digest"):
            errors.append(f"Authority body draft digest不一致: {record.get('id')}")
            continue
        artifact = load(path)
        reject_body_fields(artifact, record["path"], errors)
        if artifact.get("document_id") != record["id"] or artifact.get("observed_commit") != artifact.get("locked_commit") or artifact.get("source_state") != {"stale": False, "status": "matched"}:
            errors.append(f"Authority document identity/stale境界が不正: {record['id']}")
        if artifact.get("raw_anchor_contract") != {"fields": ["id", "locator"], "classification_status": "pending-human", "surface_ids": [], "semantic_depth_credit": False}:
            errors.append(f"Authority raw-anchor candidate境界が不正: {record['id']}")
        extraction = artifact.get("extraction", {})
        if extraction.get("tool_digest") != tool_digest or extraction.get("selector_contract") != index.get("selector_contract") or extraction.get("semantic_depth_credit") is not False or extraction.get("authority_semantics_exhaustive") is not False or extraction.get("review_status") != "automated-unreviewed":
            errors.append(f"Authority document extraction境界が不正: {record['id']}")
        current_ids = []
        for position, anchor in enumerate(artifact.get("anchors", [])):
            if not isinstance(anchor, list) or len(anchor) != 2 or not all(isinstance(value, str) for value in anchor):
                errors.append(f"Authority raw anchor tuple不整合: {record['id']}:{position}")
                continue
            candidate_id, locator = anchor
            expected_id = anchor_id(record["id"], artifact["locked_commit"], locator)
            if candidate_id != expected_id or expected_id in all_ids:
                errors.append(f"Authority raw anchor stable ID不整合: {record['id']}:{position}")
            all_ids.add(expected_id)
            current_ids.append(expected_id)
            if position == 0:
                if locator != "repository-root":
                    errors.append(f"Authority document root anchorが不正: {record['id']}")
        expected = baseline_by_id.get(record["id"], {})
        if sorted(current_ids) != expected.get("anchor_ids") or artifact.get("locked_commit") != expected.get("locked_commit") or artifact.get("tree_oid") != expected.get("tree_oid") or artifact.get("source_ids") != expected.get("source_ids"):
            errors.append(f"Authority raw-anchor専用baselineから非Mapping変更: {record['id']}")
        if record.get("anchors") != len(current_ids) or record.get("pending_human") != len(current_ids) or record.get("tree_oid") != artifact.get("tree_oid"):
            errors.append(f"Authority body index record不整合: {record['id']}")
        anchors += len(current_ids)
        source_entries += len(artifact.get("source_ids", []))
    summary = index.get("summary", {})
    expected_summary = {
        "source_entries": source_entries, "unique_documents": len(index_by_id), "matched_documents": len(index_by_id),
        "stale_documents": 0, "failed_documents": 0, "selector_exhaustive_documents": len(index_by_id),
        "raw_anchors": anchors, "classified_anchors": 0, "unclassified_anchors": anchors,
        "human_reviewed_anchors": 0, "promoted_surface_artifacts": 0, "authority_semantics_exhaustive": False,
    }
    if summary != expected_summary:
        errors.append("Authority raw-anchor summaryがArtifact実体と一致しない")
    if baseline.get("source_entries") != source_entries or baseline.get("unique_documents") != len(index_by_id):
        errors.append("Authority raw-anchor baseline denominatorがdriftしている")
    if migration != {"schema_version": 1, "baseline_id": baseline.get("id"), "replacements": []}:
        errors.append("Authority raw-anchor Migrationは未承認Mappingを含む")
    local_reference = verify_reference(reference, errors)
    result = {
        "schema_version": 1, "index": INDEX.relative_to(ROOT).as_posix(), "baseline": BASELINE.relative_to(ROOT).as_posix(),
        "methodology_reference": REFERENCE.relative_to(ROOT).as_posix(), "local_methodology_reference": local_reference,
        "summary": expected_summary, "raw_anchor_depth_credit": False, "all_candidates_pending_human": True,
        "violations": errors, "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Authority body inventory Gate失敗: " + "; ".join(errors[:20]))
    print(f"Authority body inventory Gate: documents={len(index_by_id)} raw_anchors={anchors} pending-human={anchors} promoted=0 depth-credit=0")


if __name__ == "__main__":
    main()
