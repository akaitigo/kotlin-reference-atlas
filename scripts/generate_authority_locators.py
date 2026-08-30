#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "authority" / "locator-extraction.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def surface_identity(path: Path) -> tuple[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    source_ids = [line.split(":", 1)[1].strip() for line in lines if line.startswith("source_id:")]
    if len(source_ids) != 1:
        raise RuntimeError(f"Authority Surface source_idを一意に読めない: {path}")
    return source_ids[0], sum(1 for line in lines if line.startswith("  - {id:"))


def main() -> None:
    source_lock = json.loads((ROOT / "sources.lock.yaml").read_text(encoding="utf-8"))
    locked = {item["id"]: item for item in source_lock["sources"]}
    records = []
    edge_count = 0
    for path in sorted((ROOT / "authority" / "surfaces").glob("*.authority-surfaces.yaml")):
        source_id, classified_edges = surface_identity(path)
        source = locked[source_id]
        edge_count += classified_edges
        records.append({
            "id": source["id"],
            "url": source["url"],
            "kind": source["kind"],
            "version": source["version"],
            "locked_digest": source["digest"],
            "retrieved_at": source["retrieved_at"],
            "body_evaluation_status": "deferred-source-body-not-vendored",
            "reference_edge_inventory": {
                "path": path.relative_to(ROOT).as_posix(),
                "digest": digest(path),
                "classified_edges": classified_edges,
                "classification_scope": "existing-reference-edges-not-full-authority-body",
            },
            "locator_offsets": [],
            "authority_body_exhaustive": False,
        })
    document = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "status": "incomplete-authority-body-extraction-required",
        "methodology_reference": "baseline/fe-authority-locator-reference-v1.json",
        "storage_policy": "url-metadata-digest-and-locator-offset-only",
        "separation": {
            "existing_reference_edge_classification": "authority/surfaces/*.authority-surfaces.yaml",
            "authority_body_exhaustive_extraction": False,
        },
        "summary": {
            "locked_authority_sources": len(records),
            "source_digest_matched": 0,
            "source_digest_stale": 0,
            "source_body_evaluations_deferred": len(records),
            "reference_edges_classified": edge_count,
            "unclassified_reference_edges": 0,
            "authority_body_locator_candidates": 0,
            "authority_text_surfaces_exhaustive": False,
            "human_reviewed_locator_surfaces": 0,
            "core_v2_eligible_surfaces": 0,
        },
        "sources": records,
    }
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)}: {len(records)} deferred sources, {edge_count} classified reference edges")


if __name__ == "__main__":
    main()
