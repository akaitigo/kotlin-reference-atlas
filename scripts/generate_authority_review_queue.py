#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BODY_INDEX = ROOT / "authority" / "body-inventory.snapshot.json"
QUEUE_INDEX = ROOT / "authority" / "review-queue.snapshot.json"
QUEUE_DIR = ROOT / "authority" / "review-queue-draft"
DECISIONS = ROOT / "authority" / "reviews" / "decisions.json"
PROMOTIONS = ROOT / "authority" / "reviews" / "promotions.json"
PROMOTION_BASELINE = ROOT / "baseline" / "authority-semantic-promotion-v1.json"
SOURCE_SUFFIXES = {
    ".kt", ".kts", ".java", ".js", ".mjs", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".def", ".swift", ".gradle", ".toml", ".xml", ".yml", ".yaml", ".properties",
    ".md", ".markdown", ".rst", ".adoc",
}


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def short_hash(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"ensure_ascii": False, "sort_keys": True}
    text = (json.dumps(value, separators=(",", ":"), **kwargs) if compact else json.dumps(value, indent=2, **kwargs)) + "\n"
    path.write_text(text, encoding="utf-8")


def tool_digest() -> str:
    paths = [
        "scripts/generate_authority_review_queue.py",
        "scripts/verify_authority_review_queue.py",
        "scripts/test_authority_review_queue.py",
    ]
    payload = b"".join(path.encode() + b"\0" + (ROOT / path).read_bytes() for path in paths)
    return sha256(payload)


def suggestion(anchor: dict) -> tuple[int, str, str]:
    selector = anchor["raw_selector"]
    locator = anchor["locator"]
    if selector == "document-root":
        return 0, "document-root-first-proposal", selector
    path = Path(locator)
    if path.suffix.lower() in SOURCE_SUFFIXES or path.name.lower() in {"readme", "license", "notice", "gradle.properties"}:
        return 1, "source-or-document-path-proposal", selector
    return 2, "remaining-tracked-blob-proposal", selector


def batch_id(priority: int, selector: str, anchor_id: str) -> str:
    bucket = f"{int(short_hash(anchor_id, 2), 16) % 64:02x}"
    return f"review-p{priority}-{selector}-{bucket}"


def current_semantic_ids() -> tuple[list[str], list[str]]:
    mastery = load(ROOT / "mastery.yaml")
    surfaces = sorted(item["id"] for item in mastery["surfaces"])
    behaviors = []
    for line in (ROOT / "surface.inventory.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("behavior_id:"):
            behaviors.append(stripped.split(":", 1)[1].strip())
    return surfaces, sorted(set(behaviors))


def document_binding(artifact: dict) -> dict:
    if artifact.get("fetch_url"):
        return {"document_url": artifact["fetch_url"]}
    return {"authority_url": artifact["authority_url"], "document_locator": artifact["document_locator"]}


def build() -> tuple[dict, list[dict], dict, dict]:
    body_index = load(BODY_INDEX)
    queue_tool_digest = tool_digest()
    anchors: list[tuple[dict, dict]] = []
    stale_holds, unavailable_holds = [], []
    matched_documents = 0
    for record in body_index["documents"]:
        artifact = load(ROOT / record["path"])
        fetch = artifact["fetch"]
        binding = document_binding(artifact)
        common = {
            "document_id": artifact["document_id"], **binding, "source_ids": artifact["source_ids"],
            "locked_source_digest": artifact["locked_body_digest"],
            "inventory_tool_digest": artifact["extraction"]["tool_digest"],
            "review_queue_tool_digest": queue_tool_digest,
        }
        if fetch["status"] == "matched":
            matched_documents += 1
            anchors.extend((artifact, anchor) for anchor in artifact["anchors"])
        elif fetch["status"] == "stale":
            stale_holds.append({
                **common, "locator": "document-root", "fetched_digest": fetch["fetched_digest"],
                "status": "hold-stale-document-relock-required", "reason": "locked-document-body-digest-mismatch",
            })
        else:
            unavailable_holds.append({
                **common, "error_digest": fetch["error_digest"],
                "status": "hold-unavailable-document-retrieval-required", "reason": "locked-document-body-unavailable",
            })

    all_anchor_ids = sorted(anchor["id"] for _, anchor in anchors)
    input_digest = sha256(json.dumps({
        "body_input_digest": body_index["input_digest"], "anchor_ids": all_anchor_ids,
    }, sort_keys=True, separators=(",", ":")).encode())
    queue_id = "authority-review-" + short_hash(input_digest)

    proposals = []
    cluster_groups: dict[tuple[str, str], list[str]] = {}
    for artifact, anchor in anchors:
        priority, reason, selector = suggestion(anchor)
        cluster_key = (selector, Path(anchor["locator"]).name.lower())
        cluster_groups.setdefault(cluster_key, []).append(anchor["id"])
        proposals.append((artifact, anchor, priority, reason, selector))
    cluster_by_id = {}
    for (selector, label), ids in cluster_groups.items():
        if len(ids) > 1:
            cluster = "candidate-cluster-" + short_hash(f"{selector}\0{label}")
            cluster_by_id.update({candidate_id: cluster for candidate_id in ids})

    grouped: dict[str, list[dict]] = {}
    for artifact, anchor, priority, reason, selector in proposals:
        batch = batch_id(priority, selector, anchor["id"])
        item = {
            "anchor_id": anchor["id"], "document_id": artifact["document_id"], **document_binding(artifact),
            "source_ids": artifact["source_ids"], "locked_source_digest": artifact["locked_body_digest"],
            "inventory_tool_digest": artifact["extraction"]["tool_digest"],
            "review_queue_tool_digest": queue_tool_digest, "locator": anchor["locator"],
            "locator_kind": anchor["locator_kind"], "raw_selector": anchor["raw_selector"],
            "element_name": anchor["element_name"], "parent_anchor_id": anchor["parent_anchor_id"],
            "context_start": anchor["context_start"], "context_end": anchor["context_end"],
            "context_unit": anchor["context_unit"], "context_digest": anchor["context_digest"],
            "existing_mapping_candidate_ids": [], "priority": priority, "priority_reasons": [reason],
            "candidate_cluster_id": cluster_by_id.get(anchor["id"]), "batch_id": batch, "state": "pending-human",
        }
        grouped.setdefault(batch, []).append(item)

    batches, batch_records = [], []
    for batch in sorted(grouped):
        items = sorted(grouped[batch], key=lambda item: item["anchor_id"])
        artifact = {
            "schema_version": 1, "queue_id": queue_id, "batch_id": batch, "status": "pending-human",
            "machine_assistance": "priority-cluster-and-batch-proposals-only", "semantic_decisions": "none", "items": items,
        }
        payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        parts = batch.split("-")
        priority = int(parts[1][1:])
        selector = "-".join(parts[2:-1])
        batch_records.append({
            "id": batch, "path": f"authority/review-queue-draft/{batch}.json", "digest": sha256(payload),
            "priority": priority, "raw_selector": selector, "bucket": parts[-1], "items": len(items),
        })
        batches.append(artifact)

    empty_ledger = {
        "schema_version": 1, "atlas_id": "kotlin-reference-atlas", "queue_id": queue_id,
        "status": "incomplete-human-review-required", "decisions": [],
    }
    ledger = load(DECISIONS) if DECISIONS.is_file() else empty_ledger
    if ledger.get("queue_id") != queue_id:
        if ledger.get("decisions"):
            raise RuntimeError("Authority review decision ledgerが現在のqueue IDと一致しない")
        ledger = empty_ledger
    promotions = load(PROMOTIONS) if PROMOTIONS.is_file() else {
        "schema_version": 1, "atlas_id": "kotlin-reference-atlas", "queue_id": queue_id,
        "status": "incomplete-human-review-required", "items": [],
    }
    if promotions.get("queue_id") != queue_id:
        if promotions.get("items"):
            raise RuntimeError("Authority promotion ledgerが現在のqueue IDと一致しない")
        promotions = {**promotions, "queue_id": queue_id}
    decided = {anchor for decision in ledger.get("decisions", []) for anchor in decision.get("anchor_ids", [])}
    priority_counts: dict[str, int] = {}
    for _, _, priority, _, _ in proposals:
        priority_counts[str(priority)] = priority_counts.get(str(priority), 0) + 1
    actions = [decision.get("action") for decision in ledger.get("decisions", [])]
    index = {
        "schema_version": 1, "atlas_id": "kotlin-reference-atlas", "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-human-review-required", "queue_id": queue_id, "input_digest": input_digest,
        "tool_digest": queue_tool_digest, "decision_ledger": DECISIONS.relative_to(ROOT).as_posix(),
        "body_storage": body_index["body_storage"], "machine_assistance": "priority-cluster-and-batch-proposals-only",
        "semantic_decisions": "human-only",
        "summary": {
            "eligible_documents": matched_documents, "queued_anchors": len(anchors),
            "pending_human": len(anchors) - len(decided), "human_reviewed": len(decided),
            "priority_counts": priority_counts, "candidate_clusters": len(set(cluster_by_id.values())),
            "clustered_anchors": len(cluster_by_id), "batches": len(batches),
            "stale_document_holds": len(stale_holds), "unavailable_document_holds": len(unavailable_holds),
            "decisions": len(ledger.get("decisions", [])), "included": actions.count("include"),
            "excluded": actions.count("exclude"), "merged": actions.count("merge"), "split": actions.count("split"),
            "deferred": actions.count("defer"), "authority_semantics_exhaustive": False,
            "queue_counts_as_depth_achievement": False,
        },
        "batches": batch_records, "stale_holds": sorted(stale_holds, key=lambda item: item["document_id"]),
        "unavailable_holds": sorted(unavailable_holds, key=lambda item: item["document_id"]),
    }
    return index, batches, ledger, promotions


def main(initialize_baseline: bool) -> None:
    index, batches, ledger, promotions = build()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    expected = {f"{batch['batch_id']}.json" for batch in batches}
    for path in QUEUE_DIR.glob("*.json"):
        if path.name not in expected:
            path.unlink()
    for batch in batches:
        write(QUEUE_DIR / f"{batch['batch_id']}.json", batch, compact=True)
    write(DECISIONS, ledger)
    write(PROMOTIONS, promotions)
    write(QUEUE_INDEX, index)
    if initialize_baseline:
        surfaces, behaviors = current_semantic_ids()
        write(PROMOTION_BASELINE, {
            "schema_version": 1, "id": "kotlin-authority-semantic-promotion-v1-2026-08-28",
            "captured_at": "2026-08-28T00:00:00+09:00", "mastery_surface_ids": surfaces,
            "atomic_behavior_ids": behaviors,
        })
    summary = index["summary"]
    print(f"Generated Authority review queue: anchors={summary['queued_anchors']} batches={summary['batches']} pending-human={summary['pending_human']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize-baseline", action="store_true")
    arguments = parser.parse_args()
    main(arguments.initialize_baseline)
