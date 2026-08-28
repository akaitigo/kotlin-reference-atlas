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
SCHEMA_MIGRATION = ROOT / "migrations" / "authority-body-schema-v2.json"
PIN_MIGRATION = ROOT / "migrations" / "authority-body-inventory-v1.json"
CORE_ANCHOR_MAPPING = ROOT / "migrations" / "authority-anchor-core-40f627e-to-072d7ca.json"
CORE_REPOSITORY = "https://github.com/akaitigo/reference-atlas-core.git"
CORE_OLD_COMMIT = "40f627e7e7db1d679c18f9442754951b0e1dd13b"
CORE_NEW_COMMIT = "072d7ca77981f51754e824d70c6d4ecd55ea67e5"
SELECTOR_CONTRACT = ["document-root", "tracked-blob"]
BODY_STORAGE = "digest-locator-and-metadata-only"


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def write(path: Path, value: object, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"ensure_ascii": False, "sort_keys": True}
    text = (json.dumps(value, separators=(",", ":"), **kwargs) if compact else json.dumps(value, indent=2, **kwargs)) + "\n"
    path.write_text(text, encoding="utf-8")


def git(cache: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(cache), *arguments], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def parse_git_source(source: dict) -> tuple[str, str] | None:
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/commit/([a-f0-9]{40})", source["url"])
    if not match:
        return None
    return f"https://github.com/{match.group(1)}.git", match.group(2)


def legacy_git_document_id(repository: str, commit: str) -> str:
    slug = repository.removesuffix(".git").split("github.com/", 1)[1].replace("/", "-").lower()
    identity = repository.encode() + b"\0" + commit.encode()
    return f"document-{slug}-{hashlib.sha256(identity).hexdigest()[:12]}"


def normalized_document_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def direct_document_id(source: dict) -> str:
    slug = normalized_document_id(source["id"])
    identity = f"{source['id']}\0{source['url']}\0{source['digest']}".encode()
    return f"document-{slug}-{hashlib.sha256(identity).hexdigest()[:12]}"


def anchor_id(document_identity: str, source_identity: str, locator: str) -> str:
    value = f"{document_identity}\0{source_identity}\0{locator}".encode()
    return "anchor-" + hashlib.sha256(value).hexdigest()[:20]


def root_anchor(candidate_id: str, locked_digest: str) -> dict:
    return {
        "id": candidate_id, "locator": "document-root", "locator_kind": "document-root",
        "raw_selector": "document-root", "element_name": "document-root", "parent_anchor_id": None,
        "context_start": 0, "context_end": 1, "context_unit": "byte", "context_digest": locked_digest,
        "classification_status": "pending-human", "surface_ids": [], "behavior_ids": [],
    }


def blob_anchor(candidate_id: str, root_id: str, locator: str, start: int) -> dict:
    encoded = locator.encode("utf-8", errors="surrogateescape")
    return {
        "id": candidate_id, "locator": locator, "locator_kind": "source-member",
        "raw_selector": "tracked-blob", "element_name": "tracked-blob", "parent_anchor_id": root_id,
        "context_start": start, "context_end": start + max(1, len(encoded)), "context_unit": "byte",
        "context_digest": sha256(encoded), "classification_status": "pending-human",
        "surface_ids": [], "behavior_ids": [],
    }


def extraction(tool_digest: str, method: str) -> dict:
    return {
        "method": method, "tool": "kotlin-reference-atlas-authority-body-inventory-v2",
        "tool_digest": tool_digest, "selector_contract": SELECTOR_CONTRACT,
        "selector_exhaustive_for_locked_body": True, "authority_semantics_exhaustive": False,
        "review_status": "automated-unreviewed", "body_storage": BODY_STORAGE,
    }


def fetch_matched(locked_digest: str) -> dict:
    return {"status": "matched", "fetched_digest": locked_digest, "locked_digest_match": True, "error_digest": None}


def git_document(cache_root: Path, repository: str, commit: str, sources: list[dict], tool_digest: str) -> tuple[dict, dict]:
    legacy_id = legacy_git_document_id(repository, commit)
    doc_id = normalized_document_id(legacy_id)
    cache_candidates = [cache_root / legacy_id, cache_root / doc_id]
    cache = next((item for item in cache_candidates if (item / "HEAD").exists()), cache_candidates[-1])
    if not (cache / "HEAD").exists():
        cache.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--bare", str(cache)], check=True, stdout=subprocess.DEVNULL)
    fetch_repository: str | Path = repository
    local_core = ROOT.parent / "reference-atlas-core"
    if repository == "https://github.com/akaitigo/reference-atlas-core.git" and local_core.is_dir():
        available = subprocess.run(
            ["git", "-C", str(local_core), "cat-file", "-e", f"{commit}^{{commit}}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if available.returncode == 0:
            fetch_repository = local_core
    subprocess.run(
        ["git", "-C", str(cache), "fetch", "--force", "--depth=1", "--filter=blob:none", str(fetch_repository), commit],
        check=True,
    )
    observed = git(cache, "rev-parse", "FETCH_HEAD").decode().strip()
    if observed != commit:
        raise RuntimeError(f"Authority commit stale: {doc_id} expected={commit} actual={observed}")
    tree_oid = git(cache, "rev-parse", "FETCH_HEAD^{tree}").decode().strip()
    rows = git(cache, "ls-tree", "-r", "-z", "FETCH_HEAD").split(b"\0")
    locked_digests = {item["digest"] for item in sources}
    authority_urls = {item["url"] for item in sources}
    if len(locked_digests) != 1 or len(authority_urls) != 1:
        raise RuntimeError(f"同一Git documentのSource Lock bindingが一致しない: {doc_id}")
    locked_digest = next(iter(locked_digests))
    root_id = anchor_id(legacy_id, commit, "repository-root")
    anchors = [root_anchor(root_id, locked_digest)]
    offset = 1
    blobs = []
    for row in rows:
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        _, kind, _ = metadata.decode().split(" ")
        if kind == "blob":
            blobs.append(raw_path.decode("utf-8", errors="surrogateescape"))
    for locator in sorted(blobs):
        anchors.append(blob_anchor(anchor_id(legacy_id, commit, locator), root_id, locator, offset))
        offset += max(1, len(locator.encode("utf-8", errors="surrogateescape"))) + 1
    artifact = {
        "schema_version": 1, "document_id": doc_id, "authority_url": next(iter(authority_urls)),
        "document_locator": f"git-tree:{commit}:{tree_oid}", "source_ids": sorted(item["id"] for item in sources),
        "locked_source_digest": locked_digest, "locked_body_digest": locked_digest,
        "fetch": fetch_matched(locked_digest), "extraction": extraction(tool_digest, "git-tree-metadata-selector-v2"),
        "anchors": anchors,
    }
    migration = {
        "old_document_id": legacy_id, "new_document_id": doc_id, "document_id_changed": legacy_id != doc_id,
        "stable_anchor_ids_preserved": True, "anchor_count": len(anchors),
        "anchor_id_set_digest": sha256(canonical(sorted(item["id"] for item in anchors))),
        "root_locator_change": {"from": "repository-root", "to": "document-root", "anchor_id": root_id},
        "reason": "Core v2 document identity and root-anchor schema normalization; candidate identities remain unchanged.",
    }
    return artifact, migration


def direct_document(source: dict, tool_digest: str) -> tuple[dict, dict]:
    doc_id = direct_document_id(source)
    root_id = anchor_id(doc_id, source["digest"], "document-root")
    artifact = {
        "schema_version": 1, "document_id": doc_id, "fetch_url": source["url"], "source_ids": [source["id"]],
        "locked_body_digest": source["digest"], "fetch": fetch_matched(source["digest"]),
        "extraction": extraction(tool_digest, "locked-artifact-metadata-selector-v1"),
        "anchors": [root_anchor(root_id, source["digest"])],
    }
    migration = {
        "old_document_id": None, "new_document_id": doc_id, "document_id_changed": False,
        "stable_anchor_ids_preserved": True, "anchor_count": 1,
        "anchor_id_set_digest": sha256(canonical([root_id])), "root_locator_change": None,
        "reason": "Core v2 Source Lock closure adds one pending-human metadata root for the previously unqueued locked artifact.",
    }
    return artifact, migration


def write_core_pin_migration(previous_baseline: dict, artifacts: list[tuple[dict, dict]]) -> None:
    old = next(item for item in previous_baseline["documents"] if item["source_ids"] == ["reference-atlas-core-definitive-v2"])
    current = next(item for item, _ in artifacts if item["source_ids"] == ["reference-atlas-core-definitive-v2"])
    local_core = ROOT.parent / "reference-atlas-core"
    rows = git(local_core, "ls-tree", "-r", "-z", CORE_OLD_COMMIT).split(b"\0")
    old_locators = [
        raw.split(b"\t", 1)[1].decode("utf-8", errors="surrogateescape")
        for raw in rows if raw and raw.split(b"\t", 1)[0].decode().split(" ")[1] == "blob"
    ]
    old_legacy_id = legacy_git_document_id(CORE_REPOSITORY, CORE_OLD_COMMIT)
    old_by_locator = {"document-root": anchor_id(old_legacy_id, CORE_OLD_COMMIT, "repository-root")}
    old_by_locator.update({locator: anchor_id(old_legacy_id, CORE_OLD_COMMIT, locator) for locator in old_locators})
    if set(old_by_locator.values()) != set(old["anchor_ids"]):
        raise RuntimeError("Core旧pinのAnchor集合を既存baselineから再構成できません")
    new_by_locator = {item["locator"]: item["id"] for item in current["anchors"]}
    missing = sorted(set(old_by_locator) - set(new_by_locator))
    if missing:
        raise RuntimeError(f"Core pin更新で旧Locatorが削除されています: {missing[:20]}")
    mappings = [
        {"old_anchor_id": old_by_locator[locator], "new_anchor_id": new_by_locator[locator], "locator": locator}
        for locator in sorted(old_by_locator)
    ]
    mapping = {
        "schema_version": 1,
        "id": "reference-atlas-core-40f627e-to-072d7ca-authority-anchor-mapping",
        "old_document_id": old["id"],
        "new_document_id": current["document_id"],
        "old_commit": CORE_OLD_COMMIT,
        "new_commit": CORE_NEW_COMMIT,
        "mapping_basis": "byte-exact stable git-tree locator; raw candidate IDs are replaced because the locked source commit is part of their identity",
        "old_anchor_count": len(old_by_locator),
        "new_anchor_count": len(current["anchors"]),
        "mappings": mappings,
    }
    write(CORE_ANCHOR_MAPPING, mapping)
    write(PIN_MIGRATION, {
        "schema_version": 1,
        "baseline_id": "kotlin-authority-body-inventory-v1-2026-08-28",
        "replacements": [],
    })


def main(cache_root: Path, initialize_baseline: bool) -> None:
    previous_baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if initialize_baseline and BASELINE.is_file() else None
    lock = json.loads((ROOT / "sources.lock.yaml").read_text(encoding="utf-8"))
    sources = lock["sources"]
    grouped_git: dict[tuple[str, str], list[dict]] = {}
    direct: list[dict] = []
    for source in sources:
        parsed = parse_git_source(source)
        (direct.append(source) if parsed is None else grouped_git.setdefault(parsed, []).append(source))
    tool_digest = sha256(Path(__file__).read_bytes())
    artifacts: list[tuple[dict, dict]] = []
    for (repository, commit), grouped_sources in sorted(grouped_git.items()):
        artifacts.append(git_document(cache_root, repository, commit, grouped_sources, tool_digest))
    for source in sorted(direct, key=lambda item: item["id"]):
        artifacts.append(direct_document(source, tool_digest))

    records, baseline_documents, migrations = [], [], []
    selector_counts = {selector: 0 for selector in SELECTOR_CONTRACT}
    expected_files = set()
    for artifact, migration in sorted(artifacts, key=lambda item: item[0]["document_id"]):
        doc_id = artifact["document_id"]
        path = DRAFTS / f"{doc_id}.json"
        write(path, artifact, compact=True)
        expected_files.add(path.name)
        counts: dict[str, int] = {}
        for anchor in artifact["anchors"]:
            selector = anchor["raw_selector"]
            counts[selector] = counts.get(selector, 0) + 1
            selector_counts[selector] += 1
        records.append({
            "id": doc_id, "path": path.relative_to(ROOT).as_posix(), "digest": sha256(path.read_bytes()),
            "fetch_status": artifact["fetch"]["status"], "source_entries": len(artifact["source_ids"]),
            "anchors": len(artifact["anchors"]), "anchors_by_selector": counts,
        })
        baseline_documents.append({
            "id": doc_id, "path": path.relative_to(ROOT).as_posix(), "locked_body_digest": artifact["locked_body_digest"],
            "source_ids": artifact["source_ids"], "anchor_ids": sorted(item["id"] for item in artifact["anchors"]),
        })
        migrations.append(migration)
    for path in DRAFTS.glob("*.json"):
        if path.name not in expected_files:
            path.unlink()

    total_anchors = sum(selector_counts.values())
    input_digest = sha256(canonical({
        "source_lock_digest": sha256((ROOT / "sources.lock.yaml").read_bytes()), "tool_digest": tool_digest,
        "selector_contract": SELECTOR_CONTRACT, "documents": baseline_documents,
    }))
    index = {
        "schema_version": 1, "atlas_id": "kotlin-reference-atlas", "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete-human-review-required", "input_digest": input_digest, "tool_digest": tool_digest,
        "body_storage": BODY_STORAGE, "selector_contract": SELECTOR_CONTRACT,
        "summary": {
            "source_entries": len(sources), "unique_documents": len(records), "matched_documents": len(records),
            "stale_documents": 0, "failed_documents": 0, "selector_exhaustive_documents": len(records),
            "raw_anchor_candidates": total_anchors, "anchors_by_selector": selector_counts,
            "pending_human_anchors": total_anchors, "human_reviewed_anchors": 0,
            "promoted_surface_artifacts": 0, "authority_semantics_exhaustive": False,
        },
        "documents": records,
    }
    write(INDEX, index)
    write(SCHEMA_MIGRATION, {
        "schema_version": 1, "migration_id": "kotlin-authority-body-core-v2-schema-2026-08-28",
        "from_commit": "78e8906fb6164df6fc813ef393a5303e2f83724a",
        "policy": "schema-normalization-with-stable-anchor-preservation-and-source-lock-closure", "documents": migrations,
    })
    if initialize_baseline:
        previous_core = next(
            (item for item in previous_baseline.get("documents", []) if item.get("source_ids") == ["reference-atlas-core-definitive-v2"]),
            None,
        ) if previous_baseline else None
        if previous_core and previous_core.get("locked_body_digest") == "sha256:bc469348f596574029bd45f77be3848f3ac55ed44c4aa41dba7730f920e68070":
            write_core_pin_migration(previous_baseline, artifacts)
        elif not CORE_ANCHOR_MAPPING.is_file():
            raise RuntimeError("Core pin更新の旧ID→新ID履歴Mappingがありません")
        write(PIN_MIGRATION, {
            "schema_version": 1,
            "baseline_id": "kotlin-authority-body-inventory-v1-2026-08-28",
            "replacements": [],
        })
        write(BASELINE, {
            "schema_version": 1, "id": "kotlin-authority-body-inventory-v1-2026-08-28",
            "captured_at": "2026-08-28T00:00:00+09:00", "tool_digest": tool_digest,
            "source_entries": len(sources), "unique_documents": len(records), "selector_contract": SELECTOR_CONTRACT,
            "documents": baseline_documents,
        })
    print(f"Captured Kotlin Authority candidate anchors: sources={len(sources)} documents={len(records)} anchors={total_anchors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-cache", type=Path, required=True)
    parser.add_argument("--initialize-baseline", action="store_true")
    args = parser.parse_args()
    main(args.git_cache, args.initialize_baseline)
