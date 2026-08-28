#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "authority" / "locator-extraction.json"
REFERENCE = ROOT / "baseline" / "fe-authority-locator-reference-v1.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "authority-locator-validation.json"
REFERENCE_REPOSITORY = ROOT.parent / "frontend-behavior-atlas"
FORBIDDEN_FIELDS = {
    "body", "body_text", "content", "document", "excerpt", "html", "markdown",
    "quote", "raw", "raw_body", "response_body", "source_text", "text",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def surface_identity(path: Path) -> tuple[str, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    source_ids = [line.split(":", 1)[1].strip() for line in lines if line.startswith("source_id:")]
    if len(source_ids) != 1:
        raise RuntimeError(f"Authority Surface source_idを一意に読めない: {path}")
    return source_ids[0], sum(1 for line in lines if line.startswith("  - {id:"))


def exact_keys(value: dict, expected: set[str], label: str, errors: list[str]) -> None:
    if set(value) != expected:
        errors.append(f"{label}のfield集合が不正: {sorted(value)}")


def reject_body_fields(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "_") in FORBIDDEN_FIELDS:
                errors.append(f"第三者本文fieldは禁止: {path}.{key}")
            reject_body_fields(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_body_fields(child, f"{path}[{index}]", errors)


def verify_methodology_reference(reference: dict, errors: list[str]) -> dict:
    if reference.get("git_commit") != "cabf687bab769b17928d950acc416f3f77eb4ca3":
        errors.append("FE Authority locator methodology commitが固定値と一致しない")
    if reference.get("classification") != "methodology-reference-not-completion-authority":
        errors.append("FE locator referenceをCompletion Authorityへ昇格している")
    if not REFERENCE_REPOSITORY.is_dir():
        return {"available": False, "verified": False}
    mismatches: list[str] = []
    for path, digest in sorted(reference.get("artifacts", {}).items()):
        result = subprocess.run(
            ["git", "-C", str(REFERENCE_REPOSITORY), "show", f"{reference['git_commit']}:{path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0 or sha256_bytes(result.stdout) != digest:
            mismatches.append(path)
    if mismatches:
        errors.append(f"FE locator methodology artifact digest不一致: {mismatches}")
    return {"available": True, "verified": not mismatches, "artifact_count": len(reference.get("artifacts", {}))}


def main() -> None:
    index = load_json(INDEX)
    reference = load_json(REFERENCE)
    source_lock = load_json(ROOT / "sources.lock.yaml")
    errors: list[str] = []
    reject_body_fields(index, "authority.locator-extraction", errors)
    exact_keys(index, {
        "schema_version", "atlas_id", "epoch", "status", "methodology_reference",
        "storage_policy", "separation", "summary", "sources",
    }, "Authority locator index", errors)
    exact_keys(index.get("summary", {}), {
        "locked_authority_sources", "source_digest_matched", "source_digest_stale",
        "source_body_evaluations_deferred", "reference_edges_classified",
        "unclassified_reference_edges", "authority_body_locator_candidates",
        "authority_text_surfaces_exhaustive", "human_reviewed_locator_surfaces",
        "core_v2_eligible_surfaces",
    }, "Authority locator summary", errors)
    if index.get("schema_version") != 1 or index.get("atlas_id") != "kotlin-reference-atlas":
        errors.append("Authority locator index identityが不正")
    if index.get("status") != "incomplete-authority-body-extraction-required":
        errors.append("Authority本文全体の未完状態を隠している")
    if index.get("storage_policy") != "url-metadata-digest-and-locator-offset-only":
        errors.append("Authority本文保存境界が不正")
    separation = index.get("separation", {})
    if separation.get("existing_reference_edge_classification") != "authority/surfaces/*.authority-surfaces.yaml":
        errors.append("既存reference edge分類の正本が分離されていない")
    if separation.get("authority_body_exhaustive_extraction") is not False:
        errors.append("Authority本文全体の網羅抽出を完了扱いしている")

    locked = {item["id"]: item for item in source_lock["sources"]}
    surface_paths = sorted((ROOT / "authority" / "surfaces").glob("*.authority-surfaces.yaml"))
    expected_source_ids: set[str] = set()
    reference_edges = 0
    surface_records: dict[str, tuple[Path, int]] = {}
    for path in surface_paths:
        source_id, classified_edges = surface_identity(path)
        expected_source_ids.add(source_id)
        reference_edges += classified_edges
        surface_records[source_id] = (path, classified_edges)

    records = index.get("sources", [])
    if len(records) != len({item.get("id") for item in records}):
        errors.append("Authority locator sourceに重複がある")
    if {item.get("id") for item in records} != expected_source_ids:
        errors.append("Authority locator source集合がSurface Artifactと一致しない")
    for item in records:
        exact_keys(item, {
            "id", "url", "kind", "version", "locked_digest", "retrieved_at",
            "body_evaluation_status", "reference_edge_inventory", "locator_offsets",
            "authority_body_exhaustive",
        }, f"Authority locator source {item.get('id')}", errors)
        source = locked.get(item.get("id"))
        path_and_artifact = surface_records.get(item.get("id"))
        if source is None or path_and_artifact is None:
            continue
        surface_path, classified_edges = path_and_artifact
        expected_metadata = {
            "url": source["url"], "kind": source["kind"], "version": source["version"],
            "locked_digest": source["digest"], "retrieved_at": source["retrieved_at"],
        }
        for key, expected in expected_metadata.items():
            if item.get(key) != expected:
                errors.append(f"Authority source metadata drift: {item['id']}#{key}")
        edge = item.get("reference_edge_inventory", {})
        exact_keys(edge, {"path", "digest", "classified_edges", "classification_scope"}, f"Reference edge {item['id']}", errors)
        if edge.get("path") != surface_path.relative_to(ROOT).as_posix() or edge.get("digest") != sha256_file(surface_path):
            errors.append(f"Reference edge artifact digest drift: {item['id']}")
        if edge.get("classified_edges") != classified_edges:
            errors.append(f"Reference edge count drift: {item['id']}")
        if edge.get("classification_scope") != "existing-reference-edges-not-full-authority-body":
            errors.append(f"Reference edgeを本文全体抽出として扱っている: {item['id']}")
        if item.get("body_evaluation_status") != "deferred-source-body-not-vendored":
            errors.append(f"未保持Authority bodyの評価を完了扱いしている: {item['id']}")
        if item.get("locator_offsets") != [] or item.get("authority_body_exhaustive") is not False:
            errors.append(f"本文なしでLocator offsetまたは網羅性を捏造している: {item['id']}")

    expected_summary = {
        "locked_authority_sources": len(surface_paths),
        "source_digest_matched": 0,
        "source_digest_stale": 0,
        "source_body_evaluations_deferred": len(surface_paths),
        "reference_edges_classified": reference_edges,
        "unclassified_reference_edges": 0,
        "authority_body_locator_candidates": 0,
        "authority_text_surfaces_exhaustive": False,
        "human_reviewed_locator_surfaces": 0,
        "core_v2_eligible_surfaces": 0,
    }
    if index.get("summary") != expected_summary:
        errors.append("Authority locator summaryが実体と一致しない")
    local_reference = verify_methodology_reference(reference, errors)
    result = {
        "schema_version": 1,
        "index": INDEX.relative_to(ROOT).as_posix(),
        "index_digest": sha256_file(INDEX),
        "methodology_reference": REFERENCE.relative_to(ROOT).as_posix(),
        "local_methodology_reference": local_reference,
        "body_fields_rejected": sorted(FORBIDDEN_FIELDS),
        "summary": expected_summary,
        "depth_axis_must_remain_partial": True,
        "violations": errors,
        "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("Authority locator Gate失敗: " + "; ".join(errors))
    print(f"Authority locator Gate: {reference_edges} classified edges; 0 exhaustive body surfaces; {len(surface_paths)} deferred sources; 0 human-reviewed")


if __name__ == "__main__":
    main()
