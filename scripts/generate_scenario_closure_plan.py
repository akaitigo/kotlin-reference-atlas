#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "evidence" / "scenarios" / "index.json"
PLAN = ROOT / "evidence" / "scenarios" / "closure-plan.json"
REPORT = ROOT / "artifacts" / "pattern-scenarios" / "results.json"
RISK_ORDER = ["security", "refusal", "failure", "recovery", "migration", "operations", "boundary", "performance", "compatibility", "normal"]
REQUIRED_CLOSURE = {
    "drive_pattern_scenario_and_every_variant": True,
    "first_attempt_only": True,
    "retries": 0,
    "dedicated_runtime_identity": True,
    "dedicated_oracle": True,
    "separate_trace_per_variant": True,
    "required_trace_streams": ["action", "network", "resource"],
    "separate_screenshot_per_variant": True,
    "source_and_harness_digests": True,
    "forbidden_substitutions": ["metadata-only", "capture-reuse", "integrated-trace-reuse", "mock-or-static-runtime"],
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_runtime_report() -> dict:
    return {
        "schema_version": 1,
        "id": "kotlin-pattern-scenario-runtime-gap-v1",
        "created_at": "2026-08-28T00:00:00+09:00",
        "status": "failed",
        "command": "not-run: dedicated Pattern Scenario Variant suites remain planned",
        "profile": "unexecuted-dedicated-runtime-gap",
        "counts": {"rows": 0, "variants": 0, "total": 0, "passed": 0, "failed": 0, "flaky": 0, "skipped": 0},
        "source_digest": digest(ROOT / "surface.inventory.yaml"),
        "harness_digest": digest(Path(__file__)),
        "environment": {
            "execution": "not-run",
            "compiler": "not-recorded",
            "runtime": "not-recorded",
            "platform": "not-recorded",
            "build_tool": "not-recorded",
            "architecture": "not-recorded",
            "retries": 0,
            "trace_mode": "required-but-not-recorded",
        },
        "tests": [],
    }


def generate() -> dict:
    index = load(INDEX)
    existing_report = load(REPORT) if REPORT.is_file() else None
    if existing_report and existing_report.get("status") == "passed":
        report = existing_report
    else:
        report = empty_runtime_report()
        write(REPORT, report)
    rank = {scenario: position + 1 for position, scenario in enumerate(RISK_ORDER)}
    rows = []
    for record in index["files"]:
        if record["status"] != "pattern-specific-gap":
            continue
        proof = load(ROOT / record["path"])
        rows.append({
            "id": f"closure.{proof['pattern_id']}.{proof['scenario']}",
            "pattern_id": proof["pattern_id"],
            "target_id": proof["target_id"],
            "scenario": proof["scenario"],
            "risk_rank": rank[proof["scenario"]],
            "proof": {"path": record["path"], "digest": record["digest"]},
            "variant_ids": [item["variant_id"] for item in proof["source_bindings"]],
            "required_closure": REQUIRED_CLOSURE,
            "gaps": proof["gaps"],
        })
    rows.sort(key=lambda item: (item["risk_rank"], item["pattern_id"]))
    tranches = []
    for scenario in RISK_ORDER:
        scenario_rows = [item for item in rows if item["scenario"] == scenario]
        for offset in range(0, len(scenario_rows), 4):
            selected = scenario_rows[offset:offset + 4]
            tranches.append({
                "id": f"{scenario}-{offset // 4 + 1:03d}",
                "risk_rank": rank[scenario],
                "scenario": scenario,
                "status": "planned",
                "row_ids": [item["id"] for item in selected],
                "pattern_rows": len(selected),
                "variant_runs": sum(len(item["variant_ids"]) for item in selected),
                "commit_policy": "one-reviewed-tranche-with-non-regression-runtime-identity-and-oracle-validation",
            })
    by_scenario = {scenario: sum(item["scenario"] == scenario for item in rows) for scenario in RISK_ORDER}
    plan = {
        "schema_version": 1,
        "id": "kotlin-pattern-scenario-closure-plan-v1",
        "generated_at": "2026-08-28T00:00:00+09:00",
        "status": "incomplete" if rows else "complete",
        "scope": "Every current Kotlin Pattern gap row, with all declared platform Variants and no integrated-trace substitution",
        "policy": {
            "risk_order": RISK_ORDER,
            "maximum_pattern_rows_per_tranche": 4,
            "monotonic_addition": True,
            "mass_closure_forbidden": True,
        },
        "source_digests": {
            "evidence/scenarios/index.json": digest(INDEX),
            "artifacts/pattern-scenarios/results.json": digest(REPORT),
        },
        "baseline": {
            "inherited_gap_rows_at_core_d535": len(rows),
            "matrix_rows": index["summary"]["rows"],
            "patterns": index["summary"]["patterns"],
            "scenarios": index["summary"]["scenarios"],
        },
        "summary": {
            "completed_dedicated_rows": 0,
            "remaining_rows": len(rows),
            "planned_tranches": len(tranches),
            "by_scenario": by_scenario,
        },
        "independent_incomplete": {
            "authority_atomic_rows": index["summary"]["authority_atomic_rows"],
            "external_profiles": [
                "JVM dedicated Pattern-Scenario-Variant runtime suites",
                "JS dedicated Pattern-Scenario-Variant runtime suites",
                "Wasm dedicated Pattern-Scenario-Variant runtime suites",
                "Native dedicated Pattern-Scenario-Variant runtime suites",
            ],
            "agent_forward_eval": "pass-with-independent-routing-gaps-retained",
        },
        "completed_rows": [],
        "next_tranche": tranches[0] if tranches else None,
        "tranches": tranches,
        "rows": rows,
    }
    write(PLAN, plan)
    return plan


if __name__ == "__main__":
    generated = generate()
    print(
        "Generated Scenario Closure Plan: "
        f"remaining={generated['summary']['remaining_rows']} "
        f"tranches={generated['summary']['planned_tranches']} "
        f"next={generated['next_tranche']['id'] if generated['next_tranche'] else 'none'}"
    )
