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
QUEUE_FIELDS = [
    "anchor_id", "document_id", "locator", "suggested_priority",
    "suggested_priority_reason", "suggested_cluster_id", "suggested_batch_id", "state",
]
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
    if compact:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def tool_digest() -> str:
    paths = [
        "scripts/generate_authority_review_queue.py",
        "scripts/verify_authority_review_queue.py",
        "scripts/test_authority_review_queue.py",
    ]
    payload = b"".join(path.encode() + b"\0" + (ROOT / path).read_bytes() for path in paths)
    return sha256(payload)


def suggestion(locator: str) -> tuple[int, str, str]:
    if locator == "repository-root":
        return 0, "repository-root-first-proposal", "repository-root"
    path = Path(locator)
    suffix = path.suffix.lower()
    if suffix in SOURCE_SUFFIXES or path.name.lower() in {"readme", "license", "notice", "gradle.properties"}:
        return 1, "source-or-document-path-proposal", "source-or-document"
    return 2, "remaining-tracked-blob-proposal", "tracked-blob"


def batch_id(priority: int, kind: str, anchor_id: str) -> str:
    bucket = f"{int(short_hash(anchor_id, 2), 16) % 64:02x}"
    return f"review-p{priority}-{kind}-{bucket}"


def current_semantic_ids() -> tuple[list[str], list[str]]:
    mastery = load(ROOT / "mastery.yaml")
    surfaces = sorted(item["id"] for item in mastery["surfaces"])
    behaviors = []
    for line in (ROOT / "surface.inventory.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("behavior_id:"):
            behaviors.append(stripped.split(":", 1)[1].strip())
    return surfaces, sorted(set(behaviors))


def build() -> tuple[dict, list[dict], dict, dict]:
    body_index = load(BODY_INDEX)
    queue_tool_digest = tool_digest()
    documents = []
    eligible = []
    stale_holds = []
    all_anchor_ids = []
    for record in body_index["documents"]:
        artifact = load(ROOT / record["path"])
        metadata = {
            "document_id": artifact["document_id"],
            "repository_url": artifact["repository_url"],
            "locked_commit": artifact["locked_commit"],
            "tree_oid": artifact["tree_oid"],
            "source_ids": artifact["source_ids"],
            "source_digests": artifact["source_digests"],
            "inventory_tool_digest": artifact["extraction"]["tool_digest"],
            "source_state": artifact["source_state"],
            "raw_anchors": len(artifact["anchors"]),
        }
        documents.append(metadata)
        anchor_rows = [(anchor_id, artifact["document_id"], locator) for anchor_id, locator in artifact["anchors"]]
        all_anchor_ids.extend(anchor_id for anchor_id, _, _ in anchor_rows)
        if artifact["source_state"]["stale"]:
            stale_holds.append({
                **metadata,
                "status": "hold-stale-document-relock-required",
                "reason": "locked-document-state-is-stale",
            })
        else:
            eligible.extend(anchor_rows)

    input_digest = sha256(json.dumps({
        "body_input_digest": body_index["input_digest"],
        "anchor_ids": sorted(all_anchor_ids),
    }, sort_keys=True, separators=(",", ":")).encode())
    queue_id = "authority-review-" + short_hash(input_digest)

    proposals = []
    cluster_groups: dict[tuple[str, str], list[str]] = {}
    for anchor_id, document_id, locator in eligible:
        priority, reason, kind = suggestion(locator)
        cluster_key = (kind, Path(locator).name.lower())
        cluster_groups.setdefault(cluster_key, []).append(anchor_id)
        proposals.append([anchor_id, document_id, locator, priority, reason, kind])
    cluster_by_id = {}
    for (kind, label), anchor_ids in cluster_groups.items():
        if len(anchor_ids) > 1:
            cluster = "candidate-cluster-" + short_hash(f"{kind}\0{label}")
            for anchor_id in anchor_ids:
                cluster_by_id[anchor_id] = cluster

    grouped: dict[str, list[list[object]]] = {}
    for anchor_id, document_id, locator, priority, reason, kind in proposals:
        batch = batch_id(priority, kind, anchor_id)
        item = [anchor_id, document_id, locator, priority, reason, cluster_by_id.get(anchor_id), batch, "pending-human"]
        grouped.setdefault(batch, []).append(item)
    batches = []
    batch_records = []
    for batch in sorted(grouped):
        items = sorted(grouped[batch], key=lambda item: item[0])
        artifact = {
            "schema_version": 1,
            "queue_id": queue_id,
            "batch_id": batch,
            "status": "pending-human",
            "machine_assistance": "priority-cluster-and-batch-proposals-only",
            "semantic_decisions": "none",
            "fields": QUEUE_FIELDS,
            "items": items,
        }
        payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        parts = batch.split("-")
        batches.append(artifact)
        batch_records.append({
            "id": batch,
            "path": f"authority/review-queue-draft/{batch}.json",
            "digest": sha256(payload),
            "suggested_priority": int(parts[1][1:]),
            "suggested_kind": "-".join(parts[2:-1]),
            "bucket": parts[-1],
            "items": len(items),
        })

    empty_ledger = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "queue_id": queue_id,
        "status": "incomplete-human-review-required",
        "decisions": [],
    }
    ledger = load(DECISIONS) if DECISIONS.is_file() else empty_ledger
    if ledger.get("queue_id") != queue_id:
        raise RuntimeError("Authority review decision ledgerが現在のqueue IDと一致しない")
    promotions = load(PROMOTIONS) if PROMOTIONS.is_file() else {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "queue_id": queue_id,
        "status": "incomplete-human-review-required",
        "items": [],
    }
    if promotions.get("queue_id") != queue_id:
        raise RuntimeError("Authority promotion ledgerが現在のqueue IDと一致しない")
    decided = {anchor for decision in ledger.get("decisions", []) for anchor in decision.get("anchor_ids", [])}
    priorities = {str(priority): sum(1 for item in proposals if item[3] == priority) for priority in (0, 1, 2)}
    cluster_ids = set(cluster_by_id.values())
    actions = [decision.get("action") for decision in ledger.get("decisions", [])]
    index = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-human-review-required",
        "queue_id": queue_id,
        "input_digest": input_digest,
        "tool_digest": queue_tool_digest,
        "decision_ledger": DECISIONS.relative_to(ROOT).as_posix(),
        "promotion_ledger": PROMOTIONS.relative_to(ROOT).as_posix(),
        "body_storage": "digest-locator-and-metadata-only",
        "machine_assistance": "priority-cluster-and-batch-proposals-only",
        "semantic_decisions": "human-only",
        "depth_credit": False,
        "summary": {
            "raw_anchors": len(all_anchor_ids),
            "eligible_documents": sum(1 for item in documents if not item["source_state"]["stale"]),
            "queued_anchors": len(eligible),
            "pending_human": len(eligible) - len(decided),
            "human_reviewed": len(decided),
            "suggested_priority_counts": priorities,
            "suggested_candidate_clusters": len(cluster_ids),
            "suggested_clustered_anchors": len(cluster_by_id),
            "suggested_batches": len(batches),
            "stale_document_holds": len(stale_holds),
            "stale_anchor_holds": sum(item["raw_anchors"] for item in stale_holds),
            "decisions": len(ledger.get("decisions", [])),
            "included": actions.count("include"),
            "excluded": actions.count("exclude"),
            "merged": actions.count("merge"),
            "split": actions.count("split"),
            "promoted_items": len(promotions.get("items", [])),
            "authority_semantics_exhaustive": False,
        },
        "documents": sorted(documents, key=lambda item: item["document_id"]),
        "batches": batch_records,
        "stale_holds": sorted(stale_holds, key=lambda item: item["document_id"]),
    }
    return index, batches, empty_ledger, promotions


def main(initialize_baseline: bool) -> None:
    index, batches, empty_ledger, promotions = build()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    expected = {f"{batch['batch_id']}.json" for batch in batches}
    for path in QUEUE_DIR.glob("*.json"):
        if path.name not in expected:
            path.unlink()
    for batch in batches:
        write(QUEUE_DIR / f"{batch['batch_id']}.json", batch, compact=True)
    if not DECISIONS.is_file():
        write(DECISIONS, empty_ledger)
    if not PROMOTIONS.is_file():
        write(PROMOTIONS, promotions)
    write(QUEUE_INDEX, index)
    if initialize_baseline:
        surfaces, behaviors = current_semantic_ids()
        write(PROMOTION_BASELINE, {
            "schema_version": 1,
            "id": "kotlin-authority-semantic-promotion-v1-2026-08-28",
            "captured_at": "2026-08-28T00:00:00+09:00",
            "mastery_surface_ids": surfaces,
            "atomic_behavior_ids": behaviors,
        })
    summary = index["summary"]
    print(f"Generated Authority review queue: anchors={summary['queued_anchors']} batches={summary['suggested_batches']} pending-human={summary['pending_human']} stale-holds={summary['stale_anchor_holds']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize-baseline", action="store_true")
    arguments = parser.parse_args()
    main(arguments.initialize_baseline)
