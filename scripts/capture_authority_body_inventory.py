#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "authority" / "body-inventory.snapshot.json"
DRAFTS = ROOT / "authority" / "body-inventory-draft"
BASELINE = ROOT / "baselines" / "authority-body-inventory-v1.json"
AUTHORITY_SOURCE_IDS = {
    "kotlin-spec-snapshot", "kotlin-docs-snapshot", "kotlin-keep-snapshot",
    "kotlin-compiler-source-2.4.10", "kotlin-stdlib-source-2.4.10",
    "kotlin-native-source-2.4.10", "kotlinx-coroutines-source-1.11.0",
    "kotlinx-serialization-source-snapshot", "gradle-source-9.5.0",
}
SELECTOR_CONTRACT = ["repository-root", "tracked-blob"]


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(cache: Path, *arguments: str, capture: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(cache), *arguments], check=False, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout if capture else b""


def parse_source(source: dict) -> tuple[str, str]:
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/commit/([a-f0-9]{40})", source["url"])
    if not match:
        raise RuntimeError(f"Git commit Authority URLではない: {source['id']}")
    return f"https://github.com/{match.group(1)}.git", match.group(2)


def document_id(repository: str, commit: str) -> str:
    slug = repository.removesuffix(".git").split("github.com/", 1)[1].replace("/", "-").lower()
    identity = repository.encode() + b"\0" + commit.encode()
    return f"document-{slug}-{hashlib.sha256(identity).hexdigest()[:12]}"


def anchor_id(document: str, commit: str, locator: str) -> str:
    value = f"{document}\0{commit}\0{locator}".encode()
    return "anchor-" + hashlib.sha256(value).hexdigest()[:20]


def main(cache_root: Path, initialize_baseline: bool) -> None:
    lock = json.loads((ROOT / "sources.lock.yaml").read_text(encoding="utf-8"))
    selected = [item for item in lock["sources"] if item["id"] in AUTHORITY_SOURCE_IDS]
    if {item["id"] for item in selected} != AUTHORITY_SOURCE_IDS:
        raise RuntimeError("Kotlin Authority source集合がLockと一致しない")
    grouped: dict[tuple[str, str], list[dict]] = {}
    for source in selected:
        grouped.setdefault(parse_source(source), []).append(source)
    tool_digest = sha256(Path(__file__).read_bytes())
    document_records = []
    baseline_documents = []
    total_anchors = 0
    for (repository, commit), sources in sorted(grouped.items()):
        doc_id = document_id(repository, commit)
        cache = cache_root / doc_id
        if not (cache / "HEAD").exists():
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "--bare", str(cache)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(cache), "fetch", "--force", "--depth=1", "--filter=blob:none", repository, commit], check=True)
        observed = git(cache, "rev-parse", "FETCH_HEAD").decode().strip()
        if observed != commit:
            raise RuntimeError(f"Authority commit stale: {doc_id} expected={commit} actual={observed}")
        tree_oid = git(cache, "rev-parse", "FETCH_HEAD^{tree}").decode().strip()
        rows = git(cache, "ls-tree", "-r", "-z", "FETCH_HEAD").split(b"\0")
        root_id = anchor_id(doc_id, commit, "repository-root")
        anchors = [[root_id, "repository-root"]]
        for row in rows:
            if not row:
                continue
            metadata, raw_path = row.split(b"\t", 1)
            mode, kind, object_id = metadata.decode().split(" ")
            if kind != "blob":
                continue
            locator = raw_path.decode("utf-8", errors="surrogateescape")
            anchors.append([anchor_id(doc_id, commit, locator), locator])
        anchors.sort(key=lambda item: (item[1] != "repository-root", item[1]))
        source_ids = sorted(item["id"] for item in sources)
        source_digests = sorted({item["digest"] for item in sources})
        artifact = {
            "schema_version": 1, "document_id": doc_id, "repository_url": repository,
            "locked_commit": commit, "observed_commit": observed, "source_ids": source_ids,
            "source_digests": source_digests, "tree_oid": tree_oid,
            "source_state": {"status": "matched", "stale": False},
            "raw_anchor_contract": {"fields": ["id", "locator"], "classification_status": "pending-human", "surface_ids": [], "semantic_depth_credit": False},
            "extraction": {
                "method": "git-tree-raw-anchor-selector-v1", "tool": "kotlin-reference-atlas-authority-body-inventory-v1",
                "tool_digest": tool_digest, "selector_contract": SELECTOR_CONTRACT,
                "selector_exhaustive_for_locked_tree": True, "authority_semantics_exhaustive": False,
                "review_status": "automated-unreviewed", "body_storage": "digest-locator-and-metadata-only",
                "semantic_depth_credit": False,
            },
            "anchors": anchors,
        }
        path = DRAFTS / f"{doc_id}.json"
        write(path, artifact)
        ids = sorted(item[0] for item in anchors)
        document_records.append({
            "id": doc_id, "path": path.relative_to(ROOT).as_posix(), "digest": sha256(path.read_bytes()),
            "source_entries": len(source_ids), "tree_oid": tree_oid, "anchors": len(anchors), "pending_human": len(anchors),
        })
        baseline_documents.append({
            "id": doc_id, "path": path.relative_to(ROOT).as_posix(), "locked_commit": commit,
            "tree_oid": tree_oid, "source_ids": source_ids, "anchor_ids": ids,
        })
        total_anchors += len(anchors)
    input_digest = sha256(json.dumps({"tool_digest": tool_digest, "selector_contract": SELECTOR_CONTRACT, "documents": baseline_documents}, sort_keys=True, separators=(",", ":")).encode())
    index = {
        "schema_version": 1, "atlas_id": "kotlin-reference-atlas", "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-human-review-required", "input_digest": input_digest, "tool_digest": tool_digest,
        "body_storage": "digest-locator-and-metadata-only", "selector_contract": SELECTOR_CONTRACT,
        "denominator_policy": "raw-anchor-candidates-not-semantic-surface-or-depth-credit",
        "summary": {
            "source_entries": len(selected), "unique_documents": len(document_records), "matched_documents": len(document_records),
            "stale_documents": 0, "failed_documents": 0, "selector_exhaustive_documents": len(document_records),
            "raw_anchors": total_anchors, "classified_anchors": 0, "unclassified_anchors": total_anchors,
            "human_reviewed_anchors": 0, "promoted_surface_artifacts": 0, "authority_semantics_exhaustive": False,
        },
        "documents": document_records,
    }
    write(INDEX, index)
    if initialize_baseline:
        write(BASELINE, {
            "schema_version": 1, "id": "kotlin-authority-body-inventory-v1-2026-08-28",
            "captured_at": "2026-08-28T00:00:00+09:00", "tool_digest": tool_digest,
            "source_entries": len(selected), "unique_documents": len(document_records),
            "selector_contract": SELECTOR_CONTRACT, "documents": baseline_documents,
        })
    print(f"Captured Kotlin Authority raw anchors: sources={len(selected)} documents={len(document_records)} anchors={total_anchors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-cache", type=Path, required=True)
    parser.add_argument("--initialize-baseline", action="store_true")
    args = parser.parse_args()
    main(args.git_cache, args.initialize_baseline)
