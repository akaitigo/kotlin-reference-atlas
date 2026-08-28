#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def route(query: str) -> dict:
    normalized = query.casefold()
    index = load_json(SKILL_ROOT / "references" / "capability-index.json")
    coverage = load_json(REPOSITORY_ROOT / "coverage.yaml")
    mastery = load_json(REPOSITORY_ROOT / "mastery.yaml")
    targets = {target["id"]: target for target in coverage["targets"]}
    candidates = []
    for item in index["routes"]:
        matches = [keyword for keyword in item["keywords"] if keyword.casefold() in normalized]
        if matches:
            candidates.append((len(matches), item["capability_id"], item, matches))
    if not candidates:
        return {"disposition": "gap", "reason_ja": "現在のCoverage Epochに一致する検証済みCapabilityがない。", "query": query}
    _, _, selected, matches = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
    target = targets[selected["target_id"]]
    if target["state"] != "covered":
        return {"disposition": "gap", "reason_ja": f"一致したTargetは{target['state']}で、検証済みとして利用できない。", "target_id": target["id"], "query": query}
    target_set = target["target_set"]
    outcomes = sorted(item["id"] for item in mastery["outcomes"] if target_set in item["target_sets"])
    surfaces = sorted(
        item["id"]
        for item in mastery["surfaces"]
        if item["applicability"] == "required" and target_set in item["target_sets"]
    )
    return {
        "disposition": "covered",
        "outcome_ids": outcomes,
        "surface_ids": surfaces,
        "capability_id": selected["capability_id"],
        "target_id": selected["target_id"],
        "lab": selected["lab"],
        "claim_ids": selected["claim_ids"],
        "evidence_ids": target["evidence_ids"],
        "matched_keywords": sorted(matches),
        "query": query,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kotlin AtlasのCoverageへ質問をRouteする。")
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    print(json.dumps(route(args.query), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
