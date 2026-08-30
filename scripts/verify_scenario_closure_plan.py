#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from generate_scenario_closure_plan import INDEX, PLAN, REPORT, REQUIRED_CLOSURE, RISK_ORDER, ROOT, digest


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    plan, index, report = load(PLAN), load(INDEX), load(REPORT)
    errors = []
    if plan["source_digests"] != {"evidence/scenarios/index.json": digest(INDEX), "artifacts/pattern-scenarios/results.json": digest(REPORT)}:
        errors.append("Closure Plan source digest drift")
    if report["tests"] or report["status"] != "failed" or report["counts"]["total"] != 0:
        errors.append("Unexecuted dedicated runtime report is not an explicit empty failure")
    files = {item["path"]: item for item in index["files"] if item["status"] == "pattern-specific-gap"}
    expected = []
    rank = {scenario: position + 1 for position, scenario in enumerate(RISK_ORDER)}
    for path, record in files.items():
        proof = load(ROOT / path)
        expected.append((rank[proof["scenario"]], proof["pattern_id"], proof, record))
    expected.sort(key=lambda item: (item[0], item[1]))
    if len(plan["rows"]) != len(expected):
        errors.append("Closure Plan does not contain every gap row")
    for actual, (risk_rank, pattern_id, proof, record) in zip(plan["rows"], expected):
        if actual["pattern_id"] != pattern_id or actual["scenario"] != proof["scenario"] or actual["risk_rank"] != risk_rank:
            errors.append(f"Closure row order mismatch: {actual.get('id')}")
        if actual["proof"] != {"path": record["path"], "digest": record["digest"]}:
            errors.append(f"Closure proof binding mismatch: {actual.get('id')}")
        if actual["variant_ids"] != [item["variant_id"] for item in proof["source_bindings"]]:
            errors.append(f"Closure variant denominator mismatch: {actual.get('id')}")
        if actual["required_closure"] != REQUIRED_CLOSURE or actual["gaps"] != proof["gaps"]:
            errors.append(f"Closure contract/gap mismatch: {actual.get('id')}")
    flattened = [row_id for tranche in plan["tranches"] for row_id in tranche["row_ids"]]
    if flattened != [item["id"] for item in plan["rows"]] or any(item["pattern_rows"] > 4 for item in plan["tranches"]):
        errors.append("Closure tranche order or four-row bound mismatch")
    if plan["completed_rows"] or plan["summary"]["completed_dedicated_rows"] != 0:
        errors.append("Unexecuted runtime rows were credited as completed")
    if plan["status"] != "incomplete" or plan["next_tranche"] != plan["tranches"][0]:
        errors.append("Incomplete plan next tranche mismatch")
    if errors:
        raise RuntimeError("Scenario Closure Plan Gate failed: " + "; ".join(errors[:20]))
    print(f"Scenario Closure Plan Gate: remaining={len(expected)} tranches={len(plan['tranches'])} next={plan['next_tranche']['id']} completed=0")


if __name__ == "__main__":
    main()
