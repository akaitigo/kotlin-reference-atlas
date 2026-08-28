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
SCHEMA_MIGRATION = ROOT / "migrations" / "authority-body-schema-v2.json"
CORE_PIN_MAPPINGS = [
    ROOT / "migrations" / "authority-anchor-core-e822-to-d535.json",
    ROOT / "migrations" / "authority-anchor-core-d535-to-7c9313c.json",
    ROOT / "migrations" / "authority-anchor-core-7c9313c-to-40f627e.json",
]
REFERENCE = ROOT / "baseline" / "fe-authority-body-reference-v1.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "authority-body-inventory-validation.json"
FORBIDDEN_FIELDS = {"body", "body_text", "content", "excerpt", "heading", "html", "markdown", "quote", "raw_body", "response_body", "source_text", "text"}
ANCHOR_COMMIT = "78e8906fb6164df6fc813ef393a5303e2f83724a"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


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


def historical_baseline(errors: list[str]) -> dict:
    result = subprocess.run(
        ["git", "show", f"{ANCHOR_COMMIT}:baselines/authority-body-inventory-v1.json"],
        cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        errors.append("Authority body公開済みbaseline履歴を取得できない")
        return {"documents": []}
    return json.loads(result.stdout)


def main() -> None:
    index, baseline, migration, schema_migration, reference = (
        load(INDEX), load(BASELINE), load(MIGRATION), load(SCHEMA_MIGRATION), load(REFERENCE)
    )
    errors: list[str] = []
    reject_body_fields(index, "authority.body-inventory", errors)
    tool_digest = sha256((ROOT / "scripts" / "capture_authority_body_inventory.py").read_bytes())
    if index.get("tool_digest") != tool_digest or baseline.get("tool_digest") != tool_digest:
        errors.append("Authority candidate-anchor tool digestがdriftしている")
    if index.get("selector_contract") != ["document-root", "tracked-blob"] or baseline.get("selector_contract") != index.get("selector_contract"):
        errors.append("Authority candidate-anchor selector contractがdriftしている")
    if index.get("status") != "incomplete-human-review-required" or index.get("body_storage") != "digest-locator-and-metadata-only":
        errors.append("Authority candidate-anchor未完または本文保存境界が不正")
    depth = load(ROOT / "atlas" / "definitive" / "kotlin-depth-parity.json")
    if depth.get("raw_anchor_policy") != "candidate-count-excluded-from-semantic-surface-and-depth-credit":
        errors.append("Kotlin Depth mappingがcandidate anchor非算入を固定していない")

    source_ids = {item["id"] for item in load(ROOT / "sources.lock.yaml")["sources"]}
    baseline_by_id = {item["id"]: item for item in baseline.get("documents", [])}
    index_by_id = {item["id"]: item for item in index.get("documents", [])}
    if len(baseline_by_id) != len(baseline.get("documents", [])) or set(baseline_by_id) != set(index_by_id):
        errors.append("Authority document baseline集合が削除・重複している")
    all_ids: set[str] = set()
    used_sources: set[str] = set()
    selector_counts = {"document-root": 0, "tracked-blob": 0}
    current_anchor_ids_by_document: dict[str, list[str]] = {}
    for record in index.get("documents", []):
        path = ROOT / record["path"]
        if not path.is_file() or sha256(path.read_bytes()) != record.get("digest"):
            errors.append(f"Authority body draft digest不一致: {record.get('id')}")
            continue
        artifact = load(path)
        reject_body_fields(artifact, record["path"], errors)
        if artifact.get("document_id") != record["id"] or artifact.get("fetch") != {
            "status": "matched", "fetched_digest": artifact.get("locked_body_digest"),
            "locked_digest_match": True, "error_digest": None,
        }:
            errors.append(f"Authority document identity/fetch境界が不正: {record['id']}")
        used_sources.update(artifact.get("source_ids", []))
        extraction = artifact.get("extraction", {})
        if extraction.get("tool_digest") != tool_digest or extraction.get("selector_contract") != index.get("selector_contract") or extraction.get("authority_semantics_exhaustive") is not False or extraction.get("review_status") != "automated-unreviewed":
            errors.append(f"Authority document extraction境界が不正: {record['id']}")
        current_ids = []
        local_counts: dict[str, int] = {}
        for position, anchor in enumerate(artifact.get("anchors", [])):
            candidate_id = anchor.get("id")
            selector = anchor.get("raw_selector")
            if candidate_id in all_ids or anchor.get("classification_status") != "pending-human" or anchor.get("surface_ids") != [] or anchor.get("behavior_ids") != []:
                errors.append(f"Authority candidate anchor state/ID不整合: {record['id']}:{position}")
            all_ids.add(candidate_id)
            current_ids.append(candidate_id)
            local_counts[selector] = local_counts.get(selector, 0) + 1
            selector_counts[selector] = selector_counts.get(selector, 0) + 1
            if position == 0 and (anchor.get("locator") != "document-root" or selector != "document-root" or anchor.get("parent_anchor_id") is not None or anchor.get("context_digest") != artifact.get("locked_body_digest")):
                errors.append(f"Authority document root anchorが不正: {record['id']}")
            if position > 0 and anchor.get("parent_anchor_id") != artifact["anchors"][0]["id"]:
                errors.append(f"Authority candidate anchor parentが不正: {candidate_id}")
        current_anchor_ids_by_document[record["id"]] = sorted(current_ids)
        expected = baseline_by_id.get(record["id"], {})
        if sorted(current_ids) != expected.get("anchor_ids") or artifact.get("locked_body_digest") != expected.get("locked_body_digest") or artifact.get("source_ids") != expected.get("source_ids"):
            errors.append(f"Authority candidate-anchor専用baselineから非Mapping変更: {record['id']}")
        if record.get("anchors") != len(current_ids) or record.get("anchors_by_selector") != local_counts or record.get("fetch_status") != "matched":
            errors.append(f"Authority body index record不整合: {record['id']}")
    if used_sources != source_ids:
        errors.append(f"Authority body Source Lock closure不一致: missing={sorted(source_ids - used_sources)} extra={sorted(used_sources - source_ids)}")

    summary = index.get("summary", {})
    expected_summary = {
        "source_entries": len(source_ids), "unique_documents": len(index_by_id), "matched_documents": len(index_by_id),
        "stale_documents": 0, "failed_documents": 0, "selector_exhaustive_documents": len(index_by_id),
        "raw_anchor_candidates": len(all_ids), "anchors_by_selector": selector_counts,
        "pending_human_anchors": len(all_ids), "human_reviewed_anchors": 0,
        "promoted_surface_artifacts": 0, "authority_semantics_exhaustive": False,
    }
    if summary != expected_summary:
        errors.append("Authority candidate-anchor summaryがArtifact実体と一致しない")
    if baseline.get("source_entries") != len(source_ids) or baseline.get("unique_documents") != len(index_by_id):
        errors.append("Authority candidate-anchor baseline denominatorがdriftしている")
    if migration != {"schema_version": 1, "baseline_id": baseline.get("id"), "replacements": []}:
        errors.append("現行Authority baselineに未承認replacementが含まれる")
    mappings = []
    for mapping_path in CORE_PIN_MAPPINGS:
        if not mapping_path.is_file():
            errors.append(f"Core pin更新の旧ID→新ID履歴Mappingがない: {mapping_path.name}")
            continue
        mappings.append(load(mapping_path))
    expected_chain = [
        ("e8223295bd86f7400e154171dd1596b9e54f0835", "d535b0802697edea73ca1c778a5b571e28fe0614"),
        ("d535b0802697edea73ca1c778a5b571e28fe0614", "7c9313cfb3e3149af455976228b44bbcb706bf40"),
        ("7c9313cfb3e3149af455976228b44bbcb706bf40", "40f627e7e7db1d679c18f9442754951b0e1dd13b"),
    ]
    if len(mappings) == len(expected_chain):
        previous_new_ids = None
        for mapping, (old_commit, new_commit) in zip(mappings, expected_chain):
            rows = mapping.get("mappings", [])
            old_ids = [item.get("old_anchor_id") for item in rows]
            new_ids = [item.get("new_anchor_id") for item in rows]
            if (
                mapping.get("old_commit") != old_commit
                or mapping.get("new_commit") != new_commit
                or mapping.get("old_anchor_count") != len(rows)
                or len(old_ids) != len(set(old_ids))
                or len(new_ids) != len(set(new_ids))
                or (previous_new_ids is not None and not previous_new_ids.issubset(set(old_ids)))
                or any(not item.get("locator") for item in rows)
            ):
                errors.append("Authority candidate-anchor old ID→new ID履歴Mapping実体が不正")
            previous_new_ids = set(new_ids)
        if previous_new_ids is not None and not previous_new_ids.issubset(all_ids):
            errors.append("Authority candidate-anchor最終Mappingが現行inventoryへ接続されていない")

    historical = historical_baseline(errors)
    historical_ids = {anchor for document in historical.get("documents", []) for anchor in document.get("anchor_ids", [])}
    if not historical_ids.issubset(all_ids):
        errors.append(f"公開済みcandidate anchorが欠落: {len(historical_ids - all_ids)}")
    migration_by_old = {item.get("old_document_id"): item for item in schema_migration.get("documents", []) if item.get("old_document_id")}
    for old in historical.get("documents", []):
        item = migration_by_old.get(old["id"])
        if not item or not item.get("stable_anchor_ids_preserved") or item.get("anchor_count") != len(old["anchor_ids"]):
            errors.append(f"Core v2 document/anchor移行Mappingが不足: {old['id']}")
            continue
        current_ids = current_anchor_ids_by_document.get(item["new_document_id"], [])
        if sha256(canonical(current_ids)) != item.get("anchor_id_set_digest") or current_ids != sorted(old["anchor_ids"]):
            errors.append(f"Core v2 document移行でstable anchor集合が変化: {old['id']}")
    local_reference = verify_reference(reference, errors)
    result = {
        "schema_version": 1, "index": INDEX.relative_to(ROOT).as_posix(), "baseline": BASELINE.relative_to(ROOT).as_posix(),
        "schema_migration": SCHEMA_MIGRATION.relative_to(ROOT).as_posix(), "methodology_reference": REFERENCE.relative_to(ROOT).as_posix(),
        "local_methodology_reference": local_reference, "summary": expected_summary,
        "historical_anchor_floor": len(historical_ids), "stable_historical_anchors_preserved": historical_ids.issubset(all_ids),
        "raw_anchor_depth_credit": False, "all_candidates_pending_human": True,
        "violations": errors, "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Authority body inventory Gate失敗: " + "; ".join(errors[:20]))
    print(f"Authority body inventory Gate: documents={len(index_by_id)} anchors={len(all_ids)} pending-human={len(all_ids)} historical-floor={len(historical_ids)} depth-credit=0")


if __name__ == "__main__":
    main()
