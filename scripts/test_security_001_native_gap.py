#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from capture_security_001_partial import OUTPUT, validate_generation


def expect_rejected(root: Path, mutate) -> None:
    candidate = root / "candidate"
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(OUTPUT, candidate)
    report_path = candidate / "results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutate(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        validate_generation(candidate)
    except RuntimeError:
        return
    raise RuntimeError("security-001 Native gap negative fixture was accepted")


def main() -> None:
    report = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    gaps = report.get("runtime_gaps", [])
    executed = report.get("executed_variant_ids", [])
    native_variant = "kotlin-2.4.10-native-macos-arm64"
    if report.get("execution", {}).get("executed_profile_passed") is not True:
        raise RuntimeError("executed Runtime profile is not recorded as passed")
    validate_generation(OUTPUT)

    with tempfile.TemporaryDirectory(prefix="atlas-native-gap-") as temporary:
        root = Path(temporary)
        if report.get("execution", {}).get("full_requested_profile_passed") is True:
            if gaps or native_variant not in executed:
                raise RuntimeError("successful Native Runtime execution must have no gap")
            expect_rejected(root, lambda item: item["executed_variant_ids"].remove(native_variant))
            expect_rejected(root, lambda item: item.update(runtime_gaps=[{"variant_ids": [native_variant], "completion_credit": False, "compile_only_credit": False}]))
            expect_rejected(root, lambda item: item["requested_variant_ids"].remove(native_variant))
        else:
            if len(gaps) != 1 or gaps[0].get("status") != "runtime-gap" or native_variant in executed:
                raise RuntimeError("unexecuted Native runtime gap is not explicit")
            expect_rejected(root, lambda item: item["runtime_gaps"][0].update(completion_credit=True))
            expect_rejected(root, lambda item: item.update(runtime_gaps=[]))
            expect_rejected(root, lambda item: item["executed_variant_ids"].append(native_variant))

    print("security-001 Native gap Gate: positive=1 negative=3 completion-credit=0 compile-only-credit=0")


if __name__ == "__main__":
    main()
