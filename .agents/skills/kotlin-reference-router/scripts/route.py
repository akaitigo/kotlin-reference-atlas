#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MUTATING_OUTCOMES = {"build", "operate", "troubleshoot", "evolve", "delegate"}
OUTCOME_MODES = {
    "understand": "explain", "choose": "compare", "build": "implement", "verify": "review",
    "operate": "operate", "troubleshoot": "diagnose", "evolve": "migrate", "delegate": "delegate",
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def binding(path: Path) -> dict:
    return {
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "digest": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def gap(query: str, reason: str, code: str, **extra: object) -> dict:
    return {"schema_version": 2, "disposition": "gap", "reason_code": code, "reason_ja": reason, "query": query, **extra}


def route(
    query: str,
    outcome_id: str | None = None,
    surface_id: str | None = None,
    authorized_change: bool = False,
    authority_semantic_decision: bool = False,
    stale_source_relock: bool = False,
) -> dict:
    normalized = query.casefold().strip()
    index = load_json(SKILL_ROOT / "references" / "capability-index.json")
    coverage = load_json(REPOSITORY_ROOT / "coverage.yaml")
    mastery = load_json(REPOSITORY_ROOT / "mastery.yaml")
    capabilities_entity = load_json(REPOSITORY_ROOT / "atlas" / "capabilities" / "capabilities.json")
    claims_entity = load_json(REPOSITORY_ROOT / "atlas" / "claims" / "claims.json")
    sources_entity = load_json(REPOSITORY_ROOT / "sources.lock.yaml")

    outcomes = {item["id"]: item for item in mastery["outcomes"]}
    surfaces = {item["id"]: item for item in mastery["surfaces"]}
    targets = {target["id"]: target for target in coverage["targets"]}
    capabilities = {item["id"]: item for item in capabilities_entity["capabilities"]}
    claims = {item["id"]: item for item in claims_entity["claims"]}
    sources = {item["id"]: item for item in sources_entity["sources"]}

    if outcome_id is not None and outcome_id not in outcomes:
        return gap(query, "未知のOutcomeを安全にRouteできない。", "unknown-outcome", outcome_id=outcome_id)
    if surface_id is not None and surface_id not in surfaces:
        return gap(query, "未知のSurfaceを安全にRouteできない。", "unknown-surface", surface_id=surface_id)
    if authority_semantic_decision:
        return gap(query, "Authority本文の意味判断とSemantic Surfaceへの昇格は人手Reviewが必要である。", "external-human-decision-required", outcome_id=outcome_id, surface_id=surface_id, stop_conditions=["human-authority-review-required"])
    if stale_source_relock:
        return gap(query, "stale Sourceの再固定は明示手順と人手確認なしに進めない。", "stale-source-relock-explicit-procedure-required", outcome_id=outcome_id, surface_id=surface_id, stop_conditions=["stale-source-hold", "explicit-relock-procedure-required"])
    if outcome_id in MUTATING_OUTCOMES and not authorized_change:
        return gap(query, "変更を伴うOutcomeだが、変更対象と権限が明示されていない。", "unauthorized-mutation", outcome_id=outcome_id, surface_id=surface_id, mutation={"required": True, "authorized": False, "status": "blocked"}, stop_conditions=["explicit-mutation-authorization-required"])

    candidates = []
    for item in index["routes"]:
        matches = [keyword for keyword in item["keywords"] if keyword.casefold() in normalized]
        if matches:
            candidates.append((len(matches), item["capability_id"], item, matches))
    if not candidates:
        return gap(query, "現在のCoverage Epochに一致する検証済みCapabilityがない。", "unknown-query", outcome_id=outcome_id, surface_id=surface_id, stop_conditions=["coverage-extension-or-query-clarification-required"])

    best_score = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        return gap(query, "複数Capabilityが同じ確度で一致したため、対象を推測せず停止する。", "ambiguous-query", outcome_id=outcome_id, surface_id=surface_id, candidate_capability_ids=sorted(item[1] for item in best), stop_conditions=["query-clarification-required"])

    _, _, selected, matches = best[0]
    target = targets[selected["target_id"]]
    target_set = target["target_set"]
    allowed_outcomes = sorted(item["id"] for item in mastery["outcomes"] if target_set in item["target_sets"])
    allowed_surfaces = sorted(item["id"] for item in mastery["surfaces"] if item["applicability"] == "required" and target_set in item["target_sets"])
    common = {
        "outcome_id": outcome_id, "surface_id": surface_id, "capability_id": selected["capability_id"],
        "target_id": target["id"], "target_set": target_set, "target_state": target["state"],
    }
    if outcome_id is not None and outcome_id not in allowed_outcomes:
        return gap(query, "選択したTarget setは指定OutcomeのMastery契約に含まれない。", "mastery-routing-gap", **common, target_set_allowed=False)
    if surface_id is not None and surface_id not in allowed_surfaces:
        return gap(query, "選択したTarget setは指定SurfaceのMastery契約に含まれない。", "mastery-routing-gap", **common, target_set_allowed=False)
    if target["state"] != "covered":
        return gap(query, f"一致したTargetは{target['state']}で、検証済みとして利用できない。", "target-not-covered", **common, target_requirement=target["requirement"], target_set_allowed=True, evidence_ids=target["evidence_ids"])

    capability = capabilities[selected["capability_id"]]
    claim_ids = selected["claim_ids"]
    source_ids = sorted({source_id for claim_id in claim_ids for source_id in claims[claim_id]["authority_source_ids"]})
    source_bindings = [
        {"id": source_id, "url": sources[source_id]["url"], "version": sources[source_id]["version"], "digest": sources[source_id]["digest"], "redistribution": sources[source_id]["redistribution"]}
        for source_id in source_ids
    ]
    evidence_bindings = []
    for evidence_id in target["evidence_ids"]:
        evidence_path = REPOSITORY_ROOT / "evidence" / f"{evidence_id}.evidence.json"
        if not evidence_path.is_file():
            return gap(query, "Coverageが参照するEvidence recordが存在しない。", "missing-evidence-record", target_id=target["id"], evidence_id=evidence_id)
        evidence = load_json(evidence_path)
        artifact_path = REPOSITORY_ROOT / evidence["artifact"]["uri"]
        if not artifact_path.is_file() or sha256_file(artifact_path) != evidence["artifact"]["digest"]:
            return gap(query, "Evidence artifactが存在しないかdigestが一致しない。", "stale-evidence-binding", target_id=target["id"], evidence_id=evidence_id)
        evidence_bindings.append({
            "id": evidence_id, "record": binding(evidence_path),
            "artifact": {"path": evidence["artifact"]["uri"], "digest": evidence["artifact"]["digest"], "size_bytes": evidence["artifact"]["size_bytes"]},
            "kind": evidence["kind"], "producer": evidence["producer"], "command": evidence["command"], "claim_ids": evidence["claim_ids"],
        })

    implementation_bindings = []
    for relative in selected.get("implementation_paths", [selected["lab"]]):
        implementation_path = REPOSITORY_ROOT / relative
        if implementation_path.is_file():
            implementation_bindings.append({"variant_id": relative, **binding(implementation_path)})
        elif implementation_path.is_dir():
            files = sorted(item for item in implementation_path.rglob("*") if item.is_file() and ".gradle" not in item.parts and "build" not in item.parts)
            implementation_bindings.extend({"variant_id": f"{relative}:{item.relative_to(implementation_path).as_posix()}", **binding(item)} for item in files)
    return {
        "schema_version": 2, "disposition": "covered", "status": "bounded-route", "query": query,
        "outcome_id": outcome_id, "surface_id": surface_id, "mode": OUTCOME_MODES.get(outcome_id, "route"),
        "outcome_ids": allowed_outcomes, "surface_ids": allowed_surfaces,
        "required_deliverables": surfaces[surface_id]["required_deliverables"] if surface_id else [],
        "capability_id": selected["capability_id"], "capability_verdict": capability["verdict"],
        "target_id": selected["target_id"], "target_set": target_set, "target_set_allowed": True,
        "target_state": target["state"], "target_requirement": target["requirement"], "lab": selected["lab"],
        "claim_ids": claim_ids, "evidence_ids": target["evidence_ids"], "matched_keywords": sorted(matches),
        "mutation": {"required": outcome_id in MUTATING_OUTCOMES, "authorized": authorized_change, "status": "authorized" if outcome_id in MUTATING_OUTCOMES else "not-applicable"},
        "authority_review": {"human_semantic_decision_requested": False, "stale_relock_requested": False, "status": "not-requested"},
        "implementation_bindings": implementation_bindings, "source_bindings": source_bindings,
        "evidence_bindings": evidence_bindings, "stop_conditions": [],
        "completion_semantics": "このRouteのpassはRepositoryまたはMastery completionを意味しない。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kotlin AtlasのCoverageへ質問をfail-closedでRouteする。")
    parser.add_argument("--query", required=True)
    parser.add_argument("--outcome")
    parser.add_argument("--surface")
    parser.add_argument("--authorized-change", action="store_true")
    parser.add_argument("--authority-semantic-decision", action="store_true")
    parser.add_argument("--stale-source-relock", action="store_true")
    args = parser.parse_args()
    print(json.dumps(route(args.query, args.outcome, args.surface, args.authorized_change, args.authority_semantic_decision, args.stale_source_relock), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
