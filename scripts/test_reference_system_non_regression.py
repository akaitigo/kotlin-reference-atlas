#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reference System manifestのPattern/Assertion/Runtime境界縮小を拒否する。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "integrations" / "reference-system" / "manifest.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "reference-system-non-regression.json"
SCENARIOS = {"normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility"}
REQUIRED_TOP_LEVEL = {"entry", "evidence", "runtime", "subject", "test"}
MINIMUM_PATTERN_COUNT = 69
MINIMUM_ASSERTION_COUNT = 2
MINIMUM_RUNTIME_BOUNDARY_COUNT = 4


class ManifestRegression(RuntimeError):
    pass


def validate(document: dict) -> dict:
    errors: list[str] = []
    if document.get("id") != "kotlin-automation-workbench-reference-system-v3":
        errors.append("Reference System manifest IDがv3ではない")
    missing_top = sorted(REQUIRED_TOP_LEVEL - document.keys())
    if missing_top:
        errors.append("top-level binding削除: " + ",".join(missing_top))
    scenarios = document.get("scenarios", [])
    if {item.get("id") for item in scenarios} != SCENARIOS:
        errors.append("10 Scenario集合が一致しない")
    for item in scenarios:
        identifier = item.get("id", "<unknown>")
        patterns = item.get("patterns", [])
        if len(patterns) < MINIMUM_PATTERN_COUNT or len(set(patterns)) != len(patterns):
            errors.append(f"{identifier}のPattern集合が縮小または重複")
        if len(item.get("assertions", [])) < MINIMUM_ASSERTION_COUNT:
            errors.append(f"{identifier}のAssertionが縮小")
        if len(item.get("runtime_boundaries", [])) < MINIMUM_RUNTIME_BOUNDARY_COUNT:
            errors.append(f"{identifier}のRuntime boundaryが縮小")
    if errors:
        raise ManifestRegression("; ".join(errors))
    return {
        "scenario_count": len(scenarios),
        "minimum_patterns_per_scenario": min(len(item["patterns"]) for item in scenarios),
        "minimum_assertions_per_scenario": min(len(item["assertions"]) for item in scenarios),
        "minimum_runtime_boundaries_per_scenario": min(len(item["runtime_boundaries"]) for item in scenarios),
    }


def rejected(document: dict, expected: str) -> None:
    try:
        validate(document)
    except ManifestRegression as error:
        if expected not in str(error):
            raise RuntimeError(f"Reference System negative fixtureが期待理由で拒否されない: {error}") from error
        return
    raise RuntimeError("Reference System縮小fixtureが受理された")


def main() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = validate(document)
    cases = []
    missing_pattern = copy.deepcopy(document)
    missing_pattern["scenarios"][0]["patterns"].pop()
    rejected(missing_pattern, "Pattern集合")
    cases.append({"id": "pattern-deletion", "verdict": "pass"})
    missing_assertion = copy.deepcopy(document)
    missing_assertion["scenarios"][0]["assertions"].pop()
    rejected(missing_assertion, "Assertion")
    cases.append({"id": "assertion-deletion", "verdict": "pass"})
    missing_boundary = copy.deepcopy(document)
    missing_boundary["scenarios"][0]["runtime_boundaries"].pop()
    rejected(missing_boundary, "Runtime boundary")
    cases.append({"id": "runtime-boundary-deletion", "verdict": "pass"})
    old_template = copy.deepcopy(document)
    old_template["id"] = "kotlin-automation-workbench-reference-system-v2"
    rejected(old_template, "v3")
    cases.append({"id": "old-template-downgrade", "verdict": "pass"})
    report = {"schema_version": 1, **summary, "negative_cases": cases, "negative_case_count": len(cases), "verdict": "pass"}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Reference System非後退成功: scenarios={summary['scenario_count']} patterns>={summary['minimum_patterns_per_scenario']} negative={len(cases)}")


if __name__ == "__main__":
    main()
