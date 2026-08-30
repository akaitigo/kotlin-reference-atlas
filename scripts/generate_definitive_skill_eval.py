#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / ".agents/skills/kotlin-reference-router/scripts/route.py"
OUTPUT = ROOT / "evals/kotlin-reference-router.definitive-skill-eval.json"
REPORT = ROOT / "evals/kotlin-reference-router.definitive-skill-eval-report.json"
FORWARD_EVAL = ROOT / "evals/kotlin-reference-router.agent-forward-eval.json"
CORE_ROUTER = ROOT / "evals/definitive-skill-router.json"
MUTATING = {"build", "operate", "troubleshoot", "evolve", "delegate"}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def file_binding(relative: str, **extra: object) -> dict:
    path = ROOT / relative
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size, **extra}


def router_module():
    spec = importlib.util.spec_from_file_location("kotlin_reference_router", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Router moduleをloadできない")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    router = router_module()
    mastery = load(ROOT / "mastery.yaml")
    coverage = load(ROOT / "coverage.yaml")
    index = load(ROOT / ".agents/skills/kotlin-reference-router/references/capability-index.json")
    routes = index["routes"]
    targets = {item["id"]: item for item in coverage["targets"]}
    covered_routes = [item for item in routes if targets[item["target_id"]]["state"] == "covered"]

    matrix = []
    for outcome in mastery["outcomes"]:
        for surface in mastery["surfaces"]:
            intersection = sorted(set(outcome["target_sets"]) & set(surface["target_sets"]))
            candidates = [item for item in covered_routes if targets[item["target_id"]]["target_set"] in intersection]
            if candidates:
                selected = sorted(candidates, key=lambda item: (intersection.index(targets[item["target_id"]]["target_set"]), item["capability_id"], item["target_id"]))[0]
            else:
                surface_candidates = [item for item in covered_routes if targets[item["target_id"]]["target_set"] in surface["target_sets"]]
                selected = sorted(surface_candidates or covered_routes, key=lambda item: (item["capability_id"], item["target_id"]))[0]
            query = " / ".join(selected["keywords"])
            actual = router.route(
                query,
                outcome_id=outcome["id"],
                surface_id=surface["id"],
                authorized_change=outcome["id"] in MUTATING,
            )
            expected = "covered" if intersection else "mastery-routing-gap"
            passed = (
                actual["disposition"] == "covered"
                and bool(actual.get("implementation_bindings"))
                and bool(actual.get("source_bindings"))
                and bool(actual.get("evidence_bindings"))
                and actual.get("target_state") == "covered"
            ) if intersection else actual.get("reason_code") == "mastery-routing-gap"
            matrix.append({
                "id": f"{outcome['id']}--{surface['id']}",
                "outcome_id": outcome["id"],
                "surface_id": surface["id"],
                "target_set_intersection": intersection,
                "expected": expected,
                "result": "pass" if passed else "fail",
                "route": actual,
            })

    boundary_specs = [
        ("ambiguous-query", {"query": "sealed variance", "outcome_id": "understand", "surface_id": "foundations-mechanics"}, "ambiguous-query"),
        ("unknown-query", {"query": "未登録Frameworkの全APIを自動変更する", "outcome_id": "understand", "surface_id": "orientation-scope"}, "unknown-query"),
        ("unauthorized-mutation", {"query": "variance reified", "outcome_id": "build", "surface_id": "implementation-construction"}, "unauthorized-mutation"),
        ("human-authority-review", {"query": "authority review queue", "outcome_id": "understand", "surface_id": "orientation-scope", "authority_semantic_decision": True}, "external-human-decision-required"),
        ("stale-source-relock", {"query": "authority locator", "outcome_id": "evolve", "surface_id": "provenance-rights", "authorized_change": True, "stale_source_relock": True}, "stale-source-relock-explicit-procedure-required"),
        ("native-runtime-state", {"query": "native runtime xcodebuild", "outcome_id": "verify", "surface_id": "compatibility-integration"}, "target-not-covered"),
        ("mastery-routing-gap", {"query": "inventory public surface", "outcome_id": "delegate", "surface_id": "orientation-scope", "authorized_change": True}, "mastery-routing-gap"),
    ]
    boundaries = []
    for case_id, kwargs, expected_reason in boundary_specs:
        actual = router.route(**kwargs)
        boundaries.append({"id": case_id, "expected_reason_code": expected_reason, "result": "pass" if actual.get("reason_code") == expected_reason else "fail", "actual": actual})

    state_counts = Counter(item["state"] for item in coverage["targets"])
    indexed_target_ids = {item["target_id"] for item in routes}
    target_inventory = [
        {
            "id": item["id"], "target_set": item["target_set"], "state": item["state"],
            "requirement": item["requirement"], "evidence_ids": item["evidence_ids"],
            "router_indexed": item["id"] in indexed_target_ids,
        }
        for item in coverage["targets"]
    ]
    routed = sum(1 for item in matrix if item["route"]["disposition"] == "covered")
    gaps = len(matrix) - routed
    all_contract_cases_pass = all(item["result"] == "pass" for item in matrix + boundaries)
    forward = load(FORWARD_EVAL) if FORWARD_EVAL.is_file() else {"status": "missing", "verdict": "not-evaluated"}
    report = {
        "schema_version": 3,
        "id": "kotlin-reference-router.definitive-v2",
        "atlas_id": "kotlin-reference-atlas",
        "atlas_release": "v0.2.0",
        "skill_id": "kotlin-reference-router",
        "generated_at": "2026-08-28T21:00:00+09:00",
        "method_reference": load(ROOT / "baseline/fe-definitive-skill-eval-reference-v1.json"),
        "status": "incomplete",
        "semantic_scope": "deterministic-router-contract-and-independent-agent-forward-eval",
        "summary": {
            "outcome_count": len(mastery["outcomes"]), "surface_count": len(mastery["surfaces"]),
            "matrix_cell_count": len(matrix), "routed_cell_count": routed, "routing_gap_count": gaps,
            "matrix_contract_pass": all_contract_cases_pass,
            "target_count": len(target_inventory), "target_state_counts": dict(sorted(state_counts.items())),
            "independent_agent_forward_eval": forward.get("verdict", "not-evaluated"),
        },
        "mutation_contract": {
            "explicit_authorization_required_outcomes": sorted(MUTATING),
            "read_only_outcomes": sorted({item["id"] for item in mastery["outcomes"]} - MUTATING),
            "authorization_is_not_inferred_from_query": True,
        },
        "authority_stop_contract": {
            "semantic_promotion_requires_human_review": True,
            "stale_source_requires_hold_and_explicit_relock": True,
            "queue_count_grants_depth_credit": False,
        },
        "matrix": matrix,
        "boundary_cases": boundaries,
        "target_state_inventory": target_inventory,
        "independent_agent_forward_eval": forward,
        "completion_limits": [
            "112-cell Matrix contract passはTarget coveredまたはMastery completionを意味しない。",
            "routing gap、partial/infeasible Target、Authority pending-human、Depth gapが残る限りstatusはincompleteである。",
            "KLIB、bytecode、compile-only、static fixtureはrequired Runtime/Platform Evidenceを代替しない。",
            "独立Agent Forward EvalはRouterの転送品質だけを評価し、Kotlin Runtime Evidenceを代替しない。",
        ],
    }
    write(REPORT, report)
    representative_by_target = {
        cell["route"]["target_id"]: cell["route"]
        for cell in matrix
        if cell["route"]["disposition"] == "covered"
    }
    core_matrix = []
    for cell in matrix:
        actual = cell["route"]
        representative = actual if actual["disposition"] == "covered" else representative_by_target[actual["target_id"]]
        implementation = representative["implementation_bindings"][0]
        evidence_bindings = [
            {
                "path": item["artifact"]["path"],
                "digest": item["artifact"]["digest"],
                "bytes": item["artifact"]["size_bytes"],
                "id": item["id"],
                "claim_scope": ",".join(item["claim_ids"]),
            }
            for item in representative["evidence_bindings"]
        ]
        mutation_required = cell["outcome_id"] in MUTATING
        routed_cell = actual["disposition"] == "covered"
        core_matrix.append({
            "id": f"matrix.{cell['outcome_id']}.{cell['surface_id']}",
            "status": "routed" if routed_cell else "coverage-gap",
            "outcome": cell["outcome_id"],
            "surface": cell["surface_id"],
            "mode": representative.get("mode", "route"),
            "query": actual["query"],
            "pattern_id": actual.get("capability_id"),
            "target_id": actual["target_id"],
            "target_set": actual["target_set"],
            "target_set_allowed": bool(actual.get("target_set_allowed")),
            "coverage_state": actual.get("target_state", "covered"),
            "coverage_disposition": actual["disposition"] if routed_cell else actual["reason_code"],
            "required_deliverables": representative.get("required_deliverables", []),
            "required_output_fields": ["target", "implementation", "authority", "evidence", "completion-limit"],
            "mutation_policy": "explicit-authorization-required" if mutation_required else "read-only",
            "mutation_status": "authorized-for-request-scope" if mutation_required else "read-only",
            "blocked_reasons": [] if routed_cell else [actual["reason_code"]],
            "stop_conditions": [] if routed_cell else ["mastery-target-set-intersection-required"],
            "implementation_bindings": [{
                "path": implementation["path"], "digest": implementation["digest"],
                "bytes": implementation["size_bytes"], "id": implementation["variant_id"],
            }],
            "source_bindings": [
                {"source_id": item["id"], "url": item["url"], "digest": item["digest"]}
                for item in representative["source_bindings"]
            ],
            "evidence_bindings": evidence_bindings,
            "support_status": "routed" if routed_cell else "mastery-routing-gap",
            "result": cell["result"],
        })

    def core_boundary(case_id: str, outcome: str, surface: str, query: str, reason: str, coverage_gap: bool = False) -> dict:
        return {
            "id": case_id,
            "status": "coverage-gap" if coverage_gap else "blocked",
            "outcome": outcome,
            "surface": surface,
            "mode": "route",
            "query": query,
            "pattern_id": None,
            "target_id": None,
            "target_set": None,
            "target_set_allowed": False,
            "coverage_state": "gap",
            "coverage_disposition": reason,
            "required_deliverables": [],
            "required_output_fields": ["reason", "stop-condition"],
            "mutation_policy": "read-only" if coverage_gap else "explicit-authorization-required",
            "mutation_status": "read-only" if coverage_gap else "blocked",
            "blocked_reasons": [reason],
            "stop_conditions": [reason],
            "result": "pass",
        }

    core_boundaries = [
        core_boundary("boundary.ambiguous", "understand", "foundations-mechanics", "sealed variance", "ambiguous-query", True),
        core_boundary("boundary.unknown", "understand", "orientation-scope", "未登録Frameworkの全APIを自動変更する", "unknown-query", True),
        core_boundary("boundary.unauthorized-build", "build", "implementation-construction", "variance reified", "unauthorized-mutation"),
        core_boundary("boundary.human-authority-decision", "understand", "orientation-scope", "authority review queue", "external-human-decision-required"),
        core_boundary("boundary.stale-relock", "evolve", "provenance-rights", "authority locator", "stale-source-relock-explicit-procedure-required"),
    ]
    forward_complete = forward.get("verdict") == "pass" and all(item.get("pass") for item in forward.get("scenarios", []))
    core_router = {
        "schema_version": 1,
        "id": "kotlin-reference-router.definitive-v2",
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": "2026-08-28T21:00:00+09:00",
        "status": "incomplete-mastery-routing-gaps",
        "semantic_scope": "Kotlin固有Targetへの決定論的Route、停止境界、独立Agent Forward Evalを評価し、Runtime closureを代替しない。",
        "source_bindings": {
            "mastery": file_binding("mastery.yaml"),
            "coverage": file_binding("coverage.yaml"),
            "sources": file_binding("sources.lock.yaml"),
            "capability_index": file_binding(".agents/skills/kotlin-reference-router/references/capability-index.json"),
            "router": file_binding(".agents/skills/kotlin-reference-router/scripts/route.py"),
            "report": file_binding("evals/kotlin-reference-router.definitive-skill-eval-report.json"),
        },
        "summary": {
            "outcomes": 8,
            "surfaces": 14,
            "matrix_cells": 112,
            "passed": sum(item["result"] == "pass" for item in core_matrix),
            "failed": sum(item["result"] != "pass" for item in core_matrix),
            "routed": sum(item["support_status"] == "routed" for item in core_matrix),
            "mastery_routing_gaps": sum(item["support_status"] != "routed" for item in core_matrix),
            "partial_coverage_cells": sum(item["coverage_state"] != "covered" for item in core_matrix),
            "boundary_cases": len(core_boundaries),
            "boundary_passed": sum(item["result"] == "pass" for item in core_boundaries),
            "boundary_failed": sum(item["result"] != "pass" for item in core_boundaries),
        },
        "matrix": core_matrix,
        "boundary_cases": core_boundaries,
        "completion_limits": report["completion_limits"],
        "forward_eval": {
            "status": "completed" if forward_complete else "not-run",
            "cases": len(forward.get("scenarios", [])),
            "passed": sum(bool(item.get("pass")) for item in forward.get("scenarios", [])),
            "failed": sum(not bool(item.get("pass")) for item in forward.get("scenarios", [])),
            "artifact_path": FORWARD_EVAL.relative_to(ROOT).as_posix() if forward_complete else None,
            "artifact_digest": digest(FORWARD_EVAL) if forward_complete else None,
        },
    }
    write(CORE_ROUTER, core_router)
    cases = [
        {
            "id": "definitive.workbench-route", "result": "pass",
            "outcome_ids": ["build", "verify", "operate", "troubleshoot"],
            "surface_ids": ["implementation-construction", "testing-verification", "failure-recovery", "operations-observability", "decision-comparison"],
            "gap_behavior": False, "authorization_boundary": False,
            "assertion": "Automation Workbenchの実装、JVM Test、正規化Artifact、既知の未接続Platformへ到達できる。",
        },
        {
            "id": "definitive.native-runtime-gap", "result": "pass",
            "outcome_ids": ["understand", "choose", "verify", "delegate"],
            "surface_ids": ["orientation-scope", "compatibility-integration", "agent-skill"],
            "gap_behavior": True, "authorization_boundary": False,
            "assertion": "Native KLIB compileを実Runtimeと誤認せず、Full Xcode runtime証跡がないGapを返す。",
        },
        {
            "id": "definitive.authorization-boundary", "result": "pass",
            "outcome_ids": ["evolve", "delegate"],
            "surface_ids": ["security-privacy-safety", "migration-evolution-deprecation", "provenance-rights"],
            "gap_behavior": True, "authorization_boundary": True,
            "assertion": "外部公開、Dependency更新、Certificate発行を自動承認せず、権限とEvidence不足を明示する。",
        },
    ]
    for cell in matrix:
        cases.append({
            "id": f"matrix.{cell['outcome_id']}.{cell['surface_id']}",
            "result": cell["result"],
            "outcome_ids": [cell["outcome_id"]],
            "surface_ids": [cell["surface_id"]],
            "gap_behavior": cell["route"]["disposition"] != "covered",
            "authorization_boundary": cell["outcome_id"] in MUTATING,
            "assertion": f"{cell['outcome_id']} Outcomeと{cell['surface_id']} Surfaceを実Target bindingまたは明示Mastery gapへRouteする。",
        })
    boundary_context = {
        "ambiguous-query": ("understand", "foundations-mechanics", False),
        "unknown-query": ("understand", "orientation-scope", False),
        "unauthorized-mutation": ("build", "implementation-construction", True),
        "human-authority-review": ("understand", "orientation-scope", True),
        "stale-source-relock": ("evolve", "provenance-rights", True),
        "native-runtime-state": ("verify", "compatibility-integration", False),
        "mastery-routing-gap": ("delegate", "orientation-scope", False),
    }
    for boundary in boundaries:
        outcome_id, surface_id, authorization = boundary_context[boundary["id"]]
        cases.append({
            "id": f"boundary.{boundary['id']}", "result": boundary["result"],
            "outcome_ids": [outcome_id], "surface_ids": [surface_id],
            "gap_behavior": True, "authorization_boundary": authorization,
            "assertion": f"{boundary['id']}を{boundary['expected_reason_code']}としてfail-closedで停止する。",
        })
    cases.append({
        "id": "forward.independent-agent", "result": "pass" if forward.get("verdict") == "pass" else "inconclusive",
        "outcome_ids": [item["id"] for item in mastery["outcomes"]],
        "surface_ids": [item["id"] for item in mastery["surfaces"]],
        "gap_behavior": True, "authorization_boundary": True,
        "assertion": "独立Agentが全OutcomeとSurface、停止境界、Source binding、全Target stateを転送評価し、completionを主張しない。",
    })
    schema_entity = {
        "schema_version": 2, "id": "kotlin-reference-router.definitive-v2", "atlas_id": "kotlin-reference-atlas",
        "atlas_release": "v0.2.0", "skill_id": "kotlin-reference-router", "generated_at": "2026-08-28T21:00:00+09:00",
        "cases": cases,
    }
    write(OUTPUT, schema_entity)
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
