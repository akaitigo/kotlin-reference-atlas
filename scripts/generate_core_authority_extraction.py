#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "authority" / "extraction.snapshot.json"
DRAFTS = ROOT / "authority" / "surfaces-draft"


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def dotted(value: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", value.lower()).strip("-.")


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    lock = json.loads((ROOT / "sources.lock.yaml").read_text(encoding="utf-8"))
    records = []
    input_rows = []
    for source in sorted(lock["sources"], key=lambda item: item["id"]):
        source_id = source["id"]
        suffix = dotted(source_id)
        pattern_suffix = suffix.replace(".", "-")
        edge_id = f"edge.authority.{suffix}"
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
            "domain_reference_metadata_digest": sha256(json.dumps({"id": source_id, "url": source["url"]}, sort_keys=True).encode()),
            "locator_status": "not-evaluated-fetch-failed",
            "context_digest": None,
            "context_start": None,
            "context_end": None,
            "context_unit": None,
            "heading_digest": None,
            "classification": "candidate-included-unreviewed",
        }
        draft = {
            "schema_version": 1,
            "source_id": source_id,
            "source_url": source["url"],
            "locked_source_digest": source["digest"],
            "fetch": {
                "status": "failed",
                "fetched_digest": None,
                "locked_digest_match": False,
                "http_status": None,
                "final_url": None,
                "content_type": None,
                "fetched_bytes": None,
                "error_digest": sha256(f"source-body-not-captured:{source_id}".encode()),
            },
            "extraction": {
                "method": "locked-body-locator-context-digest",
                "tool": "kotlin-reference-atlas-core-authority-extractor-v1",
                "review_status": "automated-unreviewed",
                "body_storage": "digest-and-locator-context-digest-only",
            },
            "candidate_surfaces": [candidate],
        }
        path = DRAFTS / f"{source_id}.json"
        write(path, draft)
        records.append({
            "id": source_id,
            "path": path.relative_to(ROOT).as_posix(),
            "digest": sha256(path.read_bytes()),
            "locked_digest_match": False,
            "candidate_surfaces": 1,
            "locator_status": {"not-evaluated-fetch-failed": 1},
        })
        input_rows.append({"id": source_id, "url": source["url"], "digest": source["digest"], "edge_id": edge_id})
    document = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-source-state",
        "input_digest": sha256(json.dumps(input_rows, sort_keys=True, separators=(",", ":")).encode()),
        "body_storage": "digest-and-locator-context-digest-only",
        "summary": {
            "locked_sources": len(records),
            "fetched_digest_matched": 0,
            "fetched_digest_stale": 0,
            "fetch_failed": len(records),
            "candidate_surfaces": len(records),
            "root_locators": 0,
            "fragments_found": 0,
            "fragments_not_found": 0,
            "locator_evaluations_deferred": len(records),
            "reference_edges_classified": 0,
            "unclassified_reference_edges": len(records),
            "authority_text_surfaces_exhaustive": False,
            "human_reviewed_surfaces": 0,
            "core_v2_eligible_surfaces": 0,
        },
        "sources": records,
    }
    write(OUTPUT, document)
    print(f"Generated Core Authority Extraction: {len(records)} failed/deferred source roots")


if __name__ == "__main__":
    main()
