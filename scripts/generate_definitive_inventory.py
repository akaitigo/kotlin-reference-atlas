#!/usr/bin/env python3
"""Generate the v2 Surface Inventory from reviewed authority artifacts.

The generated Claim bindings intentionally reuse bounded-v1 Claims while the
Definitive migration is incomplete. Core v2 rejects that aggregation at the
Definitive Gate; the Gap Ledger records the required one-Behavior/one-Claim
split. Generation never turns a gap into closure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "authority" / "surfaces"
OUTPUT = ROOT / "surface.inventory.yaml"
SUMMARY = ROOT / "atlas" / "definitive" / "inventory-summary.json"

CLAIM_BY_PREFIX = {
    "types.": "types.variance-nothing-reified",
    "nullability.": "types.variance-nothing-reified",
    "generics.": "types.variance-nothing-reified",
    "semantics.": "semantics.exhaustive-and-lazy",
    "contracts.": "semantics.exhaustive-and-lazy",
    "reflection.": "compiler.runtime-shapes-observable",
    "compiler.jvm": "compiler.bytecode-state-machine",
    "compiler.": "compiler.runtime-shapes-observable",
    "abi.": "evolution.compatibility-migration",
    "migration.": "migration.v1-v2-compatible",
    "mpp.": "platform.jvm-js-wasm-contract",
    "interop.c": "platform.native-test-klib",
    "interop.swift": "platform.native-test-klib",
    "interop.wasm": "platform.jvm-js-wasm-contract",
    "interop.": "interop.java-overloads-and-throws",
    "native.": "platform.native-test-klib",
    "coroutines.": "coroutines.child-failure-cancels-sibling",
    "flow.": "flow.retry-state-cancellation",
    "gradle.": "gradle.toolchain-and-artifacts-locked",
    "serialization.": "migration.v1-v2-compatible",
    "stdlib.": "semantics.exhaustive-and-lazy",
}

TARGET_BY_PREFIX = {
    "types.": "semantics.type-system",
    "nullability.": "semantics.type-system",
    "generics.": "semantics.type-system",
    "semantics.": "semantics.language-core",
    "contracts.": "semantics.language-core",
    "reflection.": "compiler.runtime-shapes",
    "compiler.jvm": "compiler.jvm-bytecode",
    "compiler.java": "interop.java-consumer",
    "compiler.incremental": "build.toolchain-lock",
    "compiler.diagnostic": "quality.failure-debugging",
    "compiler.k2": "quality.failure-debugging",
    "compiler.klib": "platform.native-compile",
    "compiler.": "compiler.runtime-shapes",
    "abi.klib": "platform.native-compile",
    "abi.": "evolution.compatibility-migration",
    "migration.": "evolution.compatibility-migration",
    "mpp.": "interop.expect-actual",
    "interop.c": "platform.native-runtime",
    "interop.swift": "platform.native-runtime",
    "interop.wasm": "platform.jvm-js-wasm-runtime",
    "interop.": "interop.java-consumer",
    "native.klib": "platform.native-compile",
    "native.": "platform.native-runtime",
    "coroutines.": "concurrency.structured-cancellation",
    "flow.": "concurrency.flow-pipelines",
    "gradle.plugin": "build.gradle-plugin-consumer",
    "gradle.": "build.toolchain-lock",
    "serialization.": "evolution.compatibility-migration",
    "stdlib.": "semantics.language-core",
}


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def claim_for(behavior_id: str) -> str:
    matches = [(prefix, claim) for prefix, claim in CLAIM_BY_PREFIX.items() if behavior_id.startswith(prefix)]
    if not matches:
        raise ValueError(f"Claim mapping is missing for {behavior_id}")
    return max(matches, key=lambda item: len(item[0]))[1]


def target_for(behavior_id: str) -> str:
    matches = [(prefix, target) for prefix, target in TARGET_BY_PREFIX.items() if behavior_id.startswith(prefix)]
    if not matches:
        raise ValueError(f"Target mapping is missing for {behavior_id}")
    return max(matches, key=lambda item: len(item[0]))[1]


def main() -> None:
    coverage = json.loads((ROOT / "coverage.yaml").read_text())
    artifacts: list[dict[str, object]] = []
    items: list[dict[str, object]] = []
    behavior_ids: set[str] = set()

    for path in sorted(AUTHORITY.glob("*.authority-surfaces.yaml")):
        document = yaml.safe_load(path.read_text())
        artifact_id = path.name.removesuffix(".authority-surfaces.yaml")
        artifacts.append(
            {
                "id": artifact_id,
                "source_id": document["source_id"],
                "path": path.relative_to(ROOT).as_posix(),
                "digest": sha256(path),
            }
        )
        for surface in document["surfaces"]:
            behavior_id = surface["behavior_id"]
            if behavior_id in behavior_ids:
                raise ValueError(f"Behavior ID is duplicated: {behavior_id}")
            behavior_ids.add(behavior_id)
            items.append(
                {
                    "id": f"inventory.{behavior_id}",
                    "authority_artifact_id": artifact_id,
                    "authority_surface_id": surface["id"],
                    "locator": surface["locator"],
                    "kind": surface["kind"],
                    "capability_id": surface["capability_id"],
                    "behavior_id": behavior_id,
                    "target_id": target_for(behavior_id),
                    "title": surface["title"],
                    "surface_ids": surface["surface_ids"],
                    "classification": "included",
                    "rationale": "公式一次資料から抽出した適用Behaviorであり、Definitive専用Proofが閉じるまでGapとして保持する。",
                    "claim_ids": [claim_for(behavior_id)],
                }
            )

    output = {
        "schema_version": 2,
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "authority_lock_digest": coverage["authority_lock_digest"],
        "authority_artifacts": artifacts,
        "items": items,
    }
    OUTPUT.write_text(yaml.safe_dump(output, allow_unicode=True, sort_keys=False, width=120))

    by_surface: dict[str, int] = {}
    for item in items:
        for surface_id in item["surface_ids"]:
            by_surface[surface_id] = by_surface.get(surface_id, 0) + 1
    summary = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "status": "incomplete",
        "authority_artifacts": len(artifacts),
        "behaviors": len(items),
        "distinct_claims_currently_reused": len({item["claim_ids"][0] for item in items}),
        "definitive_claims_required": len(items),
        "by_mastery_surface": dict(sorted(by_surface.items())),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
