#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy

from generate_authority_review_queue import build
from verify_authority_review_queue import verify_decisions


def expected_failure(label: str, decision: dict, index: dict, items: dict[str, dict], documents: dict[str, dict]) -> None:
    errors: list[str] = []
    verify_decisions(index, items, documents, errors, [decision])
    if not errors:
        raise RuntimeError(f"Authority review queue negative fixtureを拒否しなかった: {label}")


def main() -> None:
    index, batches, _, _ = build()
    item = batches[0]["items"][0]
    item_by_id = {item["anchor_id"]: item}
    document_by_id = {}
    binding_keys = [
        "anchor_id", "document_id", "document_url", "authority_url", "document_locator",
        "locked_source_digest", "inventory_tool_digest", "locator", "context_start", "context_end",
        "context_unit", "context_digest",
    ]
    binding = {key: item[key] for key in binding_keys if key in item}
    binding["review_queue_tool_digest"] = index["tool_digest"]
    valid = {
        "decision_id": "decision.fixture.manual-review",
        "action": "include",
        "anchor_ids": [item["anchor_id"]],
        "source_bindings": [binding],
        "rationale": "固定された一次資料の該当locatorを人が確認し、独立したSemantic Surfaceへ昇格できる根拠を記録した。",
        "reviewer": "human-reviewer",
        "reviewed_at": "2026-08-28T12:00:00+09:00",
        "review_method": "manual-primary-source",
        "mapping": [{"old_anchor_id": item["anchor_id"], "new_item_ids": ["reviewed.fixture-surface"]}],
        "result_items": [{"id": "reviewed.fixture-surface", "item_type": "surface"}],
    }
    errors: list[str] = []
    reviewed, promoted = verify_decisions(index, item_by_id, document_by_id, errors, [valid])
    if errors or reviewed != {item["anchor_id"]} or promoted != {"reviewed.fixture-surface": ("surface", "decision.fixture.manual-review")}:
        raise RuntimeError(f"Authority review queue valid fixtureが失敗: {errors}")

    invalid = copy.deepcopy(valid)
    invalid["reviewer"] = "automated-agent"
    expected_failure("machine-reviewer", invalid, index, item_by_id, document_by_id)
    invalid = copy.deepcopy(valid)
    invalid["reviewed_at"] = "not-a-time"
    expected_failure("review-time", invalid, index, item_by_id, document_by_id)
    invalid = copy.deepcopy(valid)
    invalid["rationale"] = "短い理由"
    expected_failure("review-reason", invalid, index, item_by_id, document_by_id)
    invalid = copy.deepcopy(valid)
    invalid["source_bindings"][0]["context_digest"] = "sha256:" + "0" * 64
    expected_failure("source-digest", invalid, index, item_by_id, document_by_id)
    invalid = copy.deepcopy(valid)
    invalid["source_bindings"][0]["locator"] = "different-locator"
    expected_failure("locator", invalid, index, item_by_id, document_by_id)
    invalid = copy.deepcopy(valid)
    invalid["mapping"][0]["new_item_ids"] = ["reviewed.other-surface"]
    expected_failure("mapping-result", invalid, index, item_by_id, document_by_id)
    if index["summary"]["queue_counts_as_depth_achievement"] is not False or any(queue_item["state"] != "pending-human" for batch in batches for queue_item in batch["items"]):
        raise RuntimeError("Authority review queue pending-human/Depth非算入fixtureが失敗")
    print("Authority review queue fixtures: valid=1 rejected=6 pending-human/depth-boundary=pass")


if __name__ == "__main__":
    main()
