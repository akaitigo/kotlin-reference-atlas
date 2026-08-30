#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Core Authority Extractionとsubject-generic body bindingを検証する。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTION = ROOT / "authority" / "extraction.snapshot.json"
SOURCE_STATE = ROOT / "authority" / "extraction-source-state.snapshot.json"
BODY_INDEX = ROOT / "authority" / "body-inventory.snapshot.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "core-authority-extraction-validation.json"
FORBIDDEN_FIELDS = {
    "body", "body_text", "content", "document", "excerpt", "heading", "html", "markdown",
    "quote", "raw", "raw_body", "response_body", "source_text", "text",
}


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


def exact_keys(value: dict, expected: set[str], label: str, errors: list[str]) -> None:
    if set(value) != expected:
        errors.append(f"{label} field集合不一致: {sorted(value)}")


def validate_data(root: Path, extraction: dict, state: dict) -> list[str]:
    errors: list[str] = []
    source_lock = load(root / "sources.lock.yaml")
    body_index = load(root / "authority" / "body-inventory.snapshot.json")
    reject_body_fields(extraction, "authority.extraction", errors)
    reject_body_fields(state, "authority.extraction-source-state", errors)

    exact_keys(state, {
        "schema_version", "atlas_id", "generated_at", "status", "storage_policy",
        "body_inventory", "summary", "sources",
    }, "Authority source-state", errors)
    if state.get("schema_version") != 1 or state.get("atlas_id") != "kotlin-reference-atlas":
        errors.append("Authority source-state identity不一致")
    if state.get("status") != "incomplete-http-transport-and-human-review-required":
        errors.append("HTTP transport/Human review gapが隠されています")
    if state.get("storage_policy") != "source-tool-document-selector-offset-and-digest-only":
        errors.append("Authority source-state storage policy不一致")
    expected_body_ref = {
        "path": "authority/body-inventory.snapshot.json",
        "digest": sha256((root / "authority" / "body-inventory.snapshot.json").read_bytes()),
        "tool_digest": body_index["tool_digest"],
        "selector_contract": body_index["selector_contract"],
    }
    if state.get("body_inventory") != expected_body_ref:
        errors.append("Authority body inventory binding digest不一致")

    body_by_source: dict[str, tuple[dict, dict]] = {}
    body_documents: set[str] = set()
    for record in body_index.get("documents", []):
        path = root / record.get("path", "")
        if not path.is_file() or sha256(path.read_bytes()) != record.get("digest"):
            errors.append(f"Authority body document digest不一致: {record.get('id')}")
            continue
        document = load(path)
        body_documents.add(record["id"])
        for source_id in document.get("source_ids", []):
            if source_id in body_by_source:
                errors.append(f"Authority source→document binding重複: {source_id}")
            body_by_source[source_id] = (record, document)

    locked = {item["id"]: item for item in source_lock["sources"]}
    extraction_by_source = {item.get("id"): item for item in extraction.get("sources", [])}
    states = state.get("sources", [])
    state_by_source = {item.get("source_id"): item for item in states}
    if len(extraction_by_source) != len(extraction.get("sources", [])) or len(state_by_source) != len(states):
        errors.append("Authority extraction/source-state Source ID重複")
    if set(extraction_by_source) != set(locked) or set(state_by_source) != set(locked) or set(body_by_source) != set(locked):
        errors.append("Authority Source Lock closure不一致")

    binary_only = 0
    matched_bindings = 0
    http_failed = 0
    root_bindings = 0
    for source_id, source in sorted(locked.items()):
        item = state_by_source.get(source_id, {})
        exact_keys(item, {
            "source_id", "source_url", "locked_source_digest", "http_transport",
            "subject_generic_acquisition", "semantic_state",
        }, f"Authority source-state {source_id}", errors)
        if item.get("source_url") != source["url"] or item.get("locked_source_digest") != source["digest"]:
            errors.append(f"Authority source-state lock identity不一致: {source_id}")
        transport = item.get("http_transport", {})
        if transport != {
            "status": "failed", "http_status": None, "final_url": None, "content_type": None,
            "fetched_bytes": None, "error_digest": sha256(f"http-source-body-not-captured:{source_id}".encode()),
        }:
            errors.append(f"HTTP fetch失敗状態が独立保存されていない: {source_id}")
        else:
            http_failed += 1

        record, document = body_by_source.get(source_id, ({}, {}))
        acquisition = item.get("subject_generic_acquisition", {})
        root_anchor = (document.get("anchors") or [{}])[0]
        expected_binary = document.get("extraction", {}).get("method") == "locked-artifact-metadata-selector-v1"
        binary_only += int(expected_binary)
        expected_acquisition = {
            "status": "matched",
            "document_id": record.get("id"),
            "document_path": record.get("path"),
            "document_digest": record.get("digest"),
            "locked_body_digest": document.get("locked_body_digest"),
            "tool": document.get("extraction", {}).get("tool"),
            "tool_digest": document.get("extraction", {}).get("tool_digest"),
            "selector_contract": document.get("extraction", {}).get("selector_contract"),
            "selector_exhaustive_for_locked_body": document.get("extraction", {}).get("selector_exhaustive_for_locked_body"),
            "binary_only": expected_binary,
            "stale": False,
            "deferred": False,
            "root_locator": {
                "anchor_id": root_anchor.get("id"), "selector": root_anchor.get("raw_selector"),
                "locator": root_anchor.get("locator"), "offset_start": root_anchor.get("context_start"),
                "offset_end": root_anchor.get("context_end"), "offset_unit": root_anchor.get("context_unit"),
                "context_digest": root_anchor.get("context_digest"),
            },
            "anchor_count": record.get("anchors"),
            "anchors_by_selector": record.get("anchors_by_selector"),
            "anchor_id_set_digest": sha256(canonical(sorted(anchor.get("id") for anchor in document.get("anchors", [])))),
        }
        if acquisition != expected_acquisition:
            errors.append(f"subject-generic acquisition/locator binding不一致: {source_id}")
        else:
            matched_bindings += 1
            root_bindings += 1
        if acquisition.get("stale") or acquisition.get("deferred"):
            errors.append(f"stale/deferred bindingをroot locatorへ使用している: {source_id}")
        semantic = item.get("semantic_state", {})
        if semantic != {
            "authority_text_surfaces_exhaustive": False,
            "human_review_status": "pending-human",
            "core_v2_eligible": False,
            "depth_credit": False,
        }:
            errors.append(f"Human reviewなしのSemantic/Core eligible昇格: {source_id}")

        index = extraction_by_source.get(source_id, {})
        draft_path = root / index.get("path", "")
        if not draft_path.is_file() or sha256(draft_path.read_bytes()) != index.get("digest"):
            errors.append(f"Core Authority draft digest不一致: {source_id}")
            continue
        draft = load(draft_path)
        reject_body_fields(draft, f"authority.surfaces-draft.{source_id}", errors)
        if draft.get("source_id") != source_id or draft.get("locked_source_digest") != source["digest"]:
            errors.append(f"Core Authority draft lock identity不一致: {source_id}")
        fetch = draft.get("fetch", {})
        if fetch.get("status") != "matched" or fetch.get("fetched_digest") != source["digest"] or fetch.get("locked_digest_match") is not True:
            errors.append(f"Core Authority acquisition projection不一致: {source_id}")
        candidates = draft.get("candidate_surfaces", [])
        if len(candidates) != 1:
            errors.append(f"Core Authority root candidate数不一致: {source_id}")
            continue
        candidate = candidates[0]
        binding_digest = sha256(canonical({
            "source_id": source_id, "document_id": record.get("id"), "document_digest": record.get("digest"),
            "anchor_id": root_anchor.get("id"), "selector": root_anchor.get("raw_selector"),
            "locator": root_anchor.get("locator"), "context_start": root_anchor.get("context_start"),
            "context_end": root_anchor.get("context_end"), "context_unit": root_anchor.get("context_unit"),
            "context_digest": root_anchor.get("context_digest"),
        }))
        if (
            candidate.get("locator_status") != "root-document"
            or candidate.get("locator") != "document-root"
            or candidate.get("context_digest") != root_anchor.get("context_digest")
            or candidate.get("context_start") != root_anchor.get("context_start")
            or candidate.get("context_end") != root_anchor.get("context_end")
            or candidate.get("context_unit") != "utf16-code-unit"
            or candidate.get("domain_reference_metadata_digest") != binding_digest
            or candidate.get("classification") != "candidate-included-unreviewed"
        ):
            errors.append(f"Core Authority root locator projection不一致: {source_id}")

    expected_state_summary = {
        "locked_sources": len(locked),
        "unique_documents": len(body_documents),
        "document_digest_matched": len(body_documents),
        "source_bindings_matched": matched_bindings,
        "http_fetch_failed": http_failed,
        "binary_only_sources": binary_only,
        "stale_source_bindings": 0,
        "deferred_source_bindings": 0,
        "root_locator_bindings": root_bindings,
        "tracked_blob_candidates": body_index.get("summary", {}).get("anchors_by_selector", {}).get("tracked-blob"),
        "authority_text_surfaces_exhaustive": False,
        "human_reviewed_sources": 0,
        "core_v2_eligible_sources": 0,
    }
    if state.get("summary") != expected_state_summary:
        errors.append("Authority source-state summaryが実体と一致しない")
    expected_extraction_summary = {
        "locked_sources": len(locked), "fetched_digest_matched": len(locked),
        "fetched_digest_stale": 0, "fetch_failed": 0, "candidate_surfaces": len(locked),
        "root_locators": len(locked), "fragments_found": 0, "fragments_not_found": 0,
        "locator_evaluations_deferred": 0, "reference_edges_classified": 0,
        "unclassified_reference_edges": len(locked), "authority_text_surfaces_exhaustive": False,
        "human_reviewed_surfaces": 0, "core_v2_eligible_surfaces": 0,
    }
    if extraction.get("status") != "incomplete-human-review-required" or extraction.get("summary") != expected_extraction_summary:
        errors.append("Core Authority extraction未完状態またはsummary不一致")
    return errors


def main() -> None:
    extraction, state = load(EXTRACTION), load(SOURCE_STATE)
    errors = validate_data(ROOT, extraction, state)
    result = {
        "schema_version": 1,
        "extraction": EXTRACTION.relative_to(ROOT).as_posix(),
        "extraction_digest": sha256(EXTRACTION.read_bytes()),
        "source_state": SOURCE_STATE.relative_to(ROOT).as_posix(),
        "source_state_digest": sha256(SOURCE_STATE.read_bytes()),
        "body_fields_rejected": sorted(FORBIDDEN_FIELDS),
        "summary": state.get("summary"),
        "semantic_depth_credit": False,
        "human_review_performed": False,
        "core_v2_eligible": False,
        "next_core_failure_reason": "unclassified-reference-edges",
        "violations": errors,
        "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Core Authority Extraction bridge Gate失敗: " + "; ".join(errors[:20]))
    summary = state["summary"]
    print(
        "Core Authority Extraction bridge Gate: "
        f"sources={summary['locked_sources']} documents={summary['unique_documents']} "
        f"matched={summary['source_bindings_matched']} http-failed={summary['http_fetch_failed']} "
        "semantic-credit=0 eligible=0"
    )


if __name__ == "__main__":
    main()
