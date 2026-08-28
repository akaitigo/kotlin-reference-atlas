#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

from generate_authority_review_queue import (
    BODY_INDEX, DECISIONS, PROMOTIONS, PROMOTION_BASELINE, QUEUE_DIR,
    QUEUE_INDEX, ROOT, build, current_semantic_ids, sha256,
)

REFERENCE = ROOT / "baseline" / "fe-authority-review-queue-reference-v1.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "authority-review-queue-validation.json"
FORBIDDEN_FIELDS = {"body", "body_text", "content", "excerpt", "heading", "html", "markdown", "quote", "raw_body", "response_body", "source_text", "text"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    expected_commit = "de2f016b8b44ea67afdb08c0552044807505984e"
    if reference.get("git_commit") != expected_commit or reference.get("classification") != "methodology-reference-not-completion-authority":
        errors.append("FE Authority review queue methodology identityが不正")
    if not repository.is_dir():
        return {"available": False, "verified": False}
    mismatches = []
    for path, expected in sorted(reference.get("artifacts", {}).items()):
        result = subprocess.run(["git", "-C", str(repository), "show", f"{expected_commit}:{path}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or sha256(result.stdout) != expected:
            mismatches.append(path)
    if mismatches:
        errors.append(f"FE Authority review queue methodology digest不一致: {mismatches}")
    return {"available": True, "verified": not mismatches, "artifact_count": len(reference.get("artifacts", {}))}


def iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        return False
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def decision_binding(item: dict, queue_tool_digest: str) -> dict:
    keys = [
        "anchor_id", "document_id", "document_url", "authority_url", "document_locator",
        "locked_source_digest", "inventory_tool_digest", "locator", "context_start", "context_end",
        "context_unit", "context_digest",
    ]
    binding = {key: item[key] for key in keys if key in item}
    binding["review_queue_tool_digest"] = queue_tool_digest
    return binding


def verify_decisions(index: dict, item_by_id: dict[str, dict], _documents: dict[str, dict], errors: list[str], decisions: list[dict] | None = None) -> tuple[set[str], dict[str, tuple[str, str]]]:
    ledger = load(DECISIONS)
    expected_keys = {"schema_version", "atlas_id", "queue_id", "status", "decisions"}
    if set(ledger) != expected_keys or ledger.get("schema_version") != 1 or ledger.get("atlas_id") != "kotlin-reference-atlas" or ledger.get("queue_id") != index["queue_id"]:
        errors.append("Authority decision ledger identity/status/fieldが不正")
    seen_decisions: set[str] = set()
    reviewed: set[str] = set()
    promoted: dict[str, tuple[str, str]] = {}
    for decision in ledger.get("decisions", []) if decisions is None else decisions:
        keys = {"decision_id", "action", "anchor_ids", "source_bindings", "rationale", "reviewer", "reviewed_at", "review_method", "mapping", "result_items"}
        decision_id = decision.get("decision_id", "")
        if set(decision) != keys or not re.fullmatch(r"decision\.[a-z0-9.-]+", decision_id) or decision_id in seen_decisions:
            errors.append(f"Decision identity/fieldが不正: {decision_id}")
        seen_decisions.add(decision_id)
        action = decision.get("action")
        if action not in {"include", "exclude", "merge", "split", "defer"}:
            errors.append(f"Decision actionが不正: {decision_id}")
        reviewer = str(decision.get("reviewer", "")).strip()
        if decision.get("review_method") != "manual-primary-source" or len(reviewer) < 2 or re.match(r"^(auto(mated)?|agent|bot|system|machine)(?:$|[-_. ])", reviewer, re.I) or len(str(decision.get("rationale", "")).strip()) < 40 or not iso_datetime(decision.get("reviewed_at")):
            errors.append(f"人手reviewer/time/reason provenanceが不足: {decision_id}")
        anchor_ids = decision.get("anchor_ids", [])
        if not anchor_ids or len(set(anchor_ids)) != len(anchor_ids) or any(anchor in reviewed or anchor not in item_by_id for anchor in anchor_ids):
            errors.append(f"Decision anchor集合がQueueと不整合: {decision_id}")
        reviewed.update(anchor_ids)
        bindings = {item.get("anchor_id"): item for item in decision.get("source_bindings", []) if isinstance(item, dict)}
        mappings = {item.get("old_anchor_id"): item for item in decision.get("mapping", []) if isinstance(item, dict)}
        if len(bindings) != len(anchor_ids) or len(mappings) != len(anchor_ids):
            errors.append(f"Decision binding/mapping cardinalityが不正: {decision_id}")
        mapping_sets = []
        for anchor_id in anchor_ids:
            item = item_by_id.get(anchor_id)
            if not item:
                continue
            if bindings.get(anchor_id) != decision_binding(item, index["tool_digest"]):
                errors.append(f"Decision digest/locator bindingがQueueと不一致: {anchor_id}")
            mapping = mappings.get(anchor_id, {})
            if set(mapping) != {"old_anchor_id", "new_item_ids"} or mapping.get("old_anchor_id") != anchor_id:
                errors.append(f"Decision mapping fieldが不正: {anchor_id}")
            new_ids = mapping.get("new_item_ids", [])
            if not isinstance(new_ids, list) or len(set(new_ids)) != len(new_ids) or any(not re.fullmatch(r"[a-z][a-z0-9.-]+", value) for value in new_ids):
                errors.append(f"Decision mapping IDが不正: {anchor_id}")
            mapping_sets.append(tuple(sorted(new_ids)))
        result_map = {}
        for result in decision.get("result_items", []):
            if set(result) != {"id", "item_type"} or not re.fullmatch(r"[a-z][a-z0-9.-]+", result.get("id", "")) or result.get("item_type") not in {"surface", "atomic-behavior"}:
                errors.append(f"Decision result itemが不正: {decision_id}")
                continue
            if result["id"] in result_map or result["id"] in promoted:
                errors.append(f"Decision result itemが重複: {result['id']}")
            result_map[result["id"]] = result["item_type"]
            promoted[result["id"]] = (result["item_type"], decision_id)
        mapped = {value for mapping in mappings.values() for value in mapping.get("new_item_ids", [])}
        if mapped != set(result_map):
            errors.append(f"Decision mapping/result整合が不正: {decision_id}")
        if action in {"exclude", "defer"} and mapped:
            errors.append(f"{action} decisionはSemantic itemへ昇格できない: {decision_id}")
        if action == "include" and (any(not values for values in mapping_sets) or len(mapped) != sum(len(values) for values in mapping_sets)):
            errors.append(f"include decision mappingが不正: {decision_id}")
        if action == "merge" and (len(anchor_ids) < 2 or not mapping_sets or len(set(mapping_sets)) != 1 or any(not values for values in mapping_sets)):
            errors.append(f"merge decision mappingが不正: {decision_id}")
        if action == "split" and (len(anchor_ids) != 1 or not mapping_sets or len(mapping_sets[0]) < 2):
            errors.append(f"split decision mappingが不正: {decision_id}")
    return reviewed, promoted


def main() -> None:
    errors: list[str] = []
    expected_index, expected_batches, _, _ = build()
    actual_index = load(QUEUE_INDEX)
    reject_body_fields(actual_index, "authority.review-queue", errors)
    if actual_index != expected_index:
        errors.append("Authority review queue indexが決定論生成値と一致しない")
    expected_files = {f"{batch['batch_id']}.json" for batch in expected_batches}
    actual_files = {path.name for path in QUEUE_DIR.glob("*.json")}
    if actual_files != expected_files:
        errors.append("Authority review batch file集合が不正")
    item_by_id: dict[str, dict] = {}
    for expected in expected_batches:
        path = QUEUE_DIR / f"{expected['batch_id']}.json"
        if not path.is_file():
            continue
        actual = load(path)
        reject_body_fields(actual, path.name, errors)
        if actual != expected:
            errors.append(f"Authority review batchが決定論生成値と不一致: {expected['batch_id']}")
        for item in actual.get("items", []):
            if not isinstance(item, dict) or item.get("state") != "pending-human" or item.get("anchor_id") in item_by_id:
                errors.append(f"Authority review item field/state/IDが不正: {expected['batch_id']}")
                continue
            item_by_id[item["anchor_id"]] = item
    raw = load(BODY_INDEX)
    raw_ids = set()
    for record in raw["documents"]:
        raw_ids.update(anchor["id"] for anchor in load(ROOT / record["path"])["anchors"])
    if set(item_by_id) != raw_ids:
        errors.append("Candidate anchor全件がQueueへ完全割当されていない")
    if actual_index.get("summary", {}).get("queue_counts_as_depth_achievement") is not False or actual_index.get("machine_assistance") != "priority-cluster-and-batch-proposals-only" or actual_index.get("semantic_decisions") != "human-only":
        errors.append("Queue件数またはmachine提案がSemantic decision/Depth creditへ昇格している")
    depth = load(ROOT / "atlas" / "definitive" / "kotlin-depth-parity.json")
    if depth.get("review_queue_policy") != "queue-count-excluded-from-semantic-surface-and-depth-credit":
        errors.append("Kotlin Depth mappingがReview Queue件数の非算入を固定していない")

    reviewed, promoted = verify_decisions(actual_index, item_by_id, {}, errors)
    promotions = load(PROMOTIONS)
    if set(promotions) != {"schema_version", "atlas_id", "queue_id", "status", "items"} or promotions.get("queue_id") != actual_index.get("queue_id"):
        errors.append("Authority promotion ledger identity/status/fieldが不正")
    actual_promotions = {}
    for item in promotions.get("items", []):
        if set(item) != {"id", "item_type", "decision_id"} or item.get("id") in actual_promotions:
            errors.append("Authority promotion item field/IDが不正")
            continue
        actual_promotions[item["id"]] = (item.get("item_type"), item.get("decision_id"))
    if actual_promotions != promoted:
        errors.append("Human decisionのmapping/resultとPromotion ledgerが一致しない")
    baseline = load(PROMOTION_BASELINE)
    current_surfaces, current_behaviors = current_semantic_ids()
    baseline_surfaces = set(baseline.get("mastery_surface_ids", []))
    baseline_behaviors = set(baseline.get("atomic_behavior_ids", []))
    if not baseline_surfaces.issubset(current_surfaces) or not baseline_behaviors.issubset(current_behaviors):
        errors.append("Authority Semantic promotion baselineが後退している")
    semantic_additions = {
        **{item: ("surface", promoted.get(item, (None, None))[1]) for item in set(current_surfaces) - baseline_surfaces},
        **{item: ("atomic-behavior", promoted.get(item, (None, None))[1]) for item in set(current_behaviors) - baseline_behaviors},
    }
    if semantic_additions != promoted:
        errors.append("Review decisionなしのSemantic Surface/Atomic behavior昇格、または実体のないresultがある")
    local_reference = verify_reference(load(REFERENCE), errors)
    summary = actual_index.get("summary", {})
    if summary.get("pending_human") != len(item_by_id) - len(reviewed) or summary.get("human_reviewed") != len(reviewed):
        errors.append("Authority review queue集計が実体と一致しない")
    result = {
        "schema_version": 1, "queue": QUEUE_INDEX.relative_to(ROOT).as_posix(),
        "decision_ledger": DECISIONS.relative_to(ROOT).as_posix(), "promotion_ledger": PROMOTIONS.relative_to(ROOT).as_posix(),
        "methodology_reference": REFERENCE.relative_to(ROOT).as_posix(), "local_methodology_reference": local_reference,
        "summary": summary, "all_raw_anchors_routed": set(item_by_id) == raw_ids,
        "queue_depth_credit": False, "violations": errors, "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Authority review queue Gate失敗: " + "; ".join(errors[:20]))
    print(f"Authority review queue Gate: anchors={len(item_by_id)} pending-human={summary['pending_human']} batches={summary['batches']} decisions={len(reviewed)} promotions={len(promoted)} depth-credit=0")


if __name__ == "__main__":
    main()
