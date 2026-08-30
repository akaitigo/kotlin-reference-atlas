#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Authority Extraction bridgeのfail-closed negative fixture。"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence" / "artifacts" / "core-authority-extraction-negative-tests.json"


spec = importlib.util.spec_from_file_location(
    "verify_core_authority_extraction",
    ROOT / "scripts" / "verify_core_authority_extraction.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expect_rejected(identifier: str, extraction: dict, state: dict, expected: str) -> dict:
    errors = module.validate_data(ROOT, extraction, state)
    if not any(expected in error for error in errors):
        raise RuntimeError(f"Authority extraction negative fixtureが拒否されません: {identifier}: {errors[:5]}")
    return {"id": identifier, "expected_reason": expected, "verdict": "rejected"}


def main() -> None:
    extraction = load(ROOT / "authority" / "extraction.snapshot.json")
    state = load(ROOT / "authority" / "extraction-source-state.snapshot.json")
    baseline_errors = module.validate_data(ROOT, extraction, state)
    if baseline_errors:
        raise RuntimeError("Authority extraction positive fixture失敗: " + "; ".join(baseline_errors[:10]))
    cases = []

    mutated = copy.deepcopy(state)
    mutated["sources"][0]["body_text"] = "forbidden-third-party-body"
    cases.append(expect_rejected("third-party-body-field", extraction, mutated, "第三者本文fieldは禁止"))

    mutated = copy.deepcopy(state)
    mutated["sources"][0]["http_transport"]["status"] = "matched"
    cases.append(expect_rejected("http-failure-hidden", extraction, mutated, "HTTP fetch失敗状態"))

    binary_index = next(index for index, item in enumerate(state["sources"]) if item["subject_generic_acquisition"]["binary_only"])
    mutated = copy.deepcopy(state)
    mutated["sources"][binary_index]["semantic_state"]["core_v2_eligible"] = True
    cases.append(expect_rejected("binary-only-promoted", extraction, mutated, "Semantic/Core eligible昇格"))

    mutated = copy.deepcopy(state)
    mutated["sources"][0]["subject_generic_acquisition"]["stale"] = True
    cases.append(expect_rejected("stale-binding-used", extraction, mutated, "stale/deferred binding"))

    mutated = copy.deepcopy(state)
    mutated["sources"][0]["subject_generic_acquisition"]["deferred"] = True
    cases.append(expect_rejected("deferred-binding-used", extraction, mutated, "stale/deferred binding"))

    mutated = copy.deepcopy(state)
    mutated["body_inventory"]["digest"] = "sha256:" + "0" * 64
    cases.append(expect_rejected("body-inventory-digest-tampered", extraction, mutated, "body inventory binding digest"))

    mutated_extraction = copy.deepcopy(extraction)
    mutated_extraction["summary"]["authority_text_surfaces_exhaustive"] = True
    cases.append(expect_rejected("semantic-exhaustive-without-review", mutated_extraction, state, "未完状態またはsummary"))

    mutated_extraction = copy.deepcopy(extraction)
    source_id = mutated_extraction["sources"][0]["id"]
    draft_path = ROOT / mutated_extraction["sources"][0]["path"]
    draft = load(draft_path)
    original = draft["candidate_surfaces"][0]["domain_reference_metadata_digest"]
    # Snapshot index digestを別Source draftへ向けるだけでもbindingを通せないことを確認する。
    mutated_extraction["sources"][0]["digest"] = "sha256:" + "f" * 64
    cases.append(expect_rejected("locator-binding-digest-tampered", mutated_extraction, state, f"draft digest不一致: {source_id}"))
    if not original.startswith("sha256:"):
        raise RuntimeError("positive fixtureのbinding digestが不正")

    report = {
        "schema_version": 1,
        "positive_cases": 1,
        "negative_cases": cases,
        "negative_case_count": len(cases),
        "semantic_depth_credit": False,
        "human_review_performed": False,
        "verdict": "pass",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Core Authority Extraction fixtures passed: positive=1 negative={len(cases)} semantic-credit=0")


if __name__ == "__main__":
    main()
