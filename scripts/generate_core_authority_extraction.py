#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Body inventoryのmetadata-only locatorをCore Authority Extractionへ接続する。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "authority" / "extraction.snapshot.json"
SOURCE_STATE = ROOT / "authority" / "extraction-source-state.snapshot.json"
BODY_INDEX = ROOT / "authority" / "body-inventory.snapshot.json"
DRAFTS = ROOT / "authority" / "surfaces-draft"
BODY_STORAGE = "digest-and-locator-context-digest-only"


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def dotted(value: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", value.lower()).strip("-.")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def body_bindings() -> tuple[dict[str, dict], dict[str, dict], dict]:
    index = load(BODY_INDEX)
    documents: dict[str, dict] = {}
    by_source: dict[str, dict] = {}
    for record in index["documents"]:
        path = ROOT / record["path"]
        if sha256(path.read_bytes()) != record["digest"]:
            raise RuntimeError(f"Authority body inventory digest drift: {record['id']}")
        document = load(path)
        if document["document_id"] != record["id"]:
            raise RuntimeError(f"Authority body document identity drift: {record['id']}")
        documents[record["id"]] = document
        for source_id in document["source_ids"]:
            if source_id in by_source:
                raise RuntimeError(f"Authority Sourceが複数documentへ接続されています: {source_id}")
            by_source[source_id] = {"record": record, "document": document}
    return by_source, documents, index


def main() -> None:
    lock = load(ROOT / "sources.lock.yaml")
    by_source, documents, body_index = body_bindings()
    tool_digest = sha256(Path(__file__).read_bytes())
    records: list[dict] = []
    input_rows: list[dict] = []
    source_states: list[dict] = []
    binary_only_sources = 0
    tracked_blob_candidates = body_index["summary"]["anchors_by_selector"]["tracked-blob"]

    for source in sorted(lock["sources"], key=lambda item: item["id"]):
        source_id = source["id"]
        binding = by_source.get(source_id)
        if binding is None:
            raise RuntimeError(f"Authority body inventoryにSourceがありません: {source_id}")
        record, document = binding["record"], binding["document"]
        if document["locked_body_digest"] != source["digest"]:
            raise RuntimeError(f"Authority body/source lock digest mismatch: {source_id}")
        if document["fetch"] != {
            "status": "matched", "fetched_digest": source["digest"],
            "locked_digest_match": True, "error_digest": None,
        }:
            raise RuntimeError(f"Authority body acquisition is not matched: {source_id}")
        root = document["anchors"][0]
        if root["raw_selector"] != "document-root" or root["locator"] != "document-root":
            raise RuntimeError(f"Authority body root locator drift: {source_id}")
        counts = record["anchors_by_selector"]
        binary_only = document["extraction"]["method"] == "locked-artifact-metadata-selector-v1"
        binary_only_sources += int(binary_only)

        suffix = dotted(source_id)
        pattern_suffix = suffix.replace(".", "-")
        edge_id = f"edge.authority.{suffix}"
        binding_digest = sha256(canonical({
            "source_id": source_id, "document_id": record["id"], "document_digest": record["digest"],
            "anchor_id": root["id"], "selector": root["raw_selector"], "locator": root["locator"],
            "context_start": root["context_start"], "context_end": root["context_end"],
            "context_unit": root["context_unit"], "context_digest": root["context_digest"],
        }))
        candidate = {
            "edge_id": edge_id,
            "source_id": source_id,
            "reference_url": source["url"],
            "locator": "document-root",
            "pattern_id": f"authority/{pattern_suffix}",
            "pattern_kind": "atomic",
            "candidate_behavior_id": f"candidate.authority.{suffix}",
            "capability_id": "authority.locator-extraction",
            "target_id": "authority.locator-extraction",
            "claim_id": "authority.locator-inventory-is-copyright-safe-and-incomplete",
            "variant_ids": [f"variant.authority.{suffix}.locked"],
            "surface_ids": ["provenance-rights"],
            "classification_basis": "domain-contract-projection-unreviewed",
            "domain_reference_metadata_digest": binding_digest,
            "locator_status": "root-document",
            "context_digest": root["context_digest"],
            "context_start": root["context_start"],
            "context_end": root["context_end"],
            # Core candidate schema uses UTF-16 offsets. The root sentinel is
            # 0..1 in both the subject-generic byte contract and this projection.
            "context_unit": "utf16-code-unit",
            "heading_digest": None,
            "classification": "candidate-included-unreviewed",
        }
        draft = {
            "schema_version": 1,
            "source_id": source_id,
            "source_url": source["url"],
            "locked_source_digest": source["digest"],
            "fetch": {
                "status": "matched",
                "fetched_digest": source["digest"],
                "locked_digest_match": True,
                "http_status": None,
                "final_url": None,
                "content_type": "application/vnd.reference-atlas.locked-metadata+json",
                "fetched_bytes": None,
                "error_digest": None,
            },
            "extraction": {
                "method": "locked-body-locator-context-digest",
                "tool": "kotlin-reference-atlas-core-authority-extractor-v2",
                "tool_digest": tool_digest,
                "review_status": "automated-unreviewed",
                "body_storage": BODY_STORAGE,
            },
            "candidate_surfaces": [candidate],
        }
        path = DRAFTS / f"{source_id}.json"
        write(path, draft)
        records.append({
            "id": source_id,
            "path": path.relative_to(ROOT).as_posix(),
            "digest": sha256(path.read_bytes()),
            "locked_digest_match": True,
            "candidate_surfaces": 1,
            "locator_status": {"root-document": 1},
        })
        source_states.append({
            "source_id": source_id,
            "source_url": source["url"],
            "locked_source_digest": source["digest"],
            "http_transport": {
                "status": "failed",
                "http_status": None,
                "final_url": None,
                "content_type": None,
                "fetched_bytes": None,
                "error_digest": sha256(f"http-source-body-not-captured:{source_id}".encode()),
            },
            "subject_generic_acquisition": {
                "status": "matched",
                "document_id": record["id"],
                "document_path": record["path"],
                "document_digest": record["digest"],
                "locked_body_digest": document["locked_body_digest"],
                "tool": document["extraction"]["tool"],
                "tool_digest": document["extraction"]["tool_digest"],
                "selector_contract": document["extraction"]["selector_contract"],
                "selector_exhaustive_for_locked_body": document["extraction"]["selector_exhaustive_for_locked_body"],
                "binary_only": binary_only,
                "stale": False,
                "deferred": False,
                "root_locator": {
                    "anchor_id": root["id"],
                    "selector": root["raw_selector"],
                    "locator": root["locator"],
                    "offset_start": root["context_start"],
                    "offset_end": root["context_end"],
                    "offset_unit": root["context_unit"],
                    "context_digest": root["context_digest"],
                },
                "anchor_count": record["anchors"],
                "anchors_by_selector": counts,
                "anchor_id_set_digest": sha256(canonical(sorted(item["id"] for item in document["anchors"]))),
            },
            "semantic_state": {
                "authority_text_surfaces_exhaustive": False,
                "human_review_status": "pending-human",
                "core_v2_eligible": False,
                "depth_credit": False,
            },
        })
        input_rows.append({
            "source_id": source_id, "source_digest": source["digest"],
            "document_id": record["id"], "document_digest": record["digest"],
            "root_anchor_id": root["id"], "binding_digest": binding_digest,
        })

    state = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-http-transport-and-human-review-required",
        "storage_policy": "source-tool-document-selector-offset-and-digest-only",
        "body_inventory": {
            "path": BODY_INDEX.relative_to(ROOT).as_posix(),
            "digest": sha256(BODY_INDEX.read_bytes()),
            "tool_digest": body_index["tool_digest"],
            "selector_contract": body_index["selector_contract"],
        },
        "summary": {
            "locked_sources": len(source_states),
            "unique_documents": len(documents),
            "document_digest_matched": len(documents),
            "source_bindings_matched": len(source_states),
            "http_fetch_failed": len(source_states),
            "binary_only_sources": binary_only_sources,
            "stale_source_bindings": 0,
            "deferred_source_bindings": 0,
            "root_locator_bindings": len(source_states),
            "tracked_blob_candidates": tracked_blob_candidates,
            "authority_text_surfaces_exhaustive": False,
            "human_reviewed_sources": 0,
            "core_v2_eligible_sources": 0,
        },
        "sources": source_states,
    }
    write(SOURCE_STATE, state)
    document = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-human-review-required",
        "input_digest": sha256(canonical({
            "source_lock": sha256((ROOT / "sources.lock.yaml").read_bytes()),
            "body_inventory": sha256(BODY_INDEX.read_bytes()),
            "source_state": sha256(SOURCE_STATE.read_bytes()),
            "tool_digest": tool_digest,
            "bindings": input_rows,
        })),
        "tool_digest": tool_digest,
        "body_storage": BODY_STORAGE,
        "summary": {
            "locked_sources": len(records),
            "fetched_digest_matched": len(records),
            "fetched_digest_stale": 0,
            "fetch_failed": 0,
            "candidate_surfaces": len(records),
            "root_locators": len(records),
            "fragments_found": 0,
            "fragments_not_found": 0,
            "locator_evaluations_deferred": 0,
            "reference_edges_classified": 0,
            "unclassified_reference_edges": len(records),
            "authority_text_surfaces_exhaustive": False,
            "human_reviewed_surfaces": 0,
            "core_v2_eligible_surfaces": 0,
        },
        "sources": records,
    }
    write(OUTPUT, document)
    print(
        "Generated Core Authority Extraction bridge: "
        f"sources={len(records)} documents={len(documents)} matched={len(records)} "
        f"http-failed={len(source_states)} binary-only={binary_only_sources} eligible=0"
    )


if __name__ == "__main__":
    main()
