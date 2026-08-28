#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from atomic_evidence import EvidencePublishError, publish_directory

ROOT = Path(__file__).resolve().parents[1]


def verify_fe_reference() -> None:
    reference = json.loads((ROOT / "baseline" / "fe-atomic-evidence-reference-v1.json").read_text(encoding="utf-8"))
    repository = ROOT.parent / "frontend-behavior-atlas"
    for path, expected in reference["artifacts"].items():
        result = subprocess.run(
            ["git", "-C", str(repository), "show", f"{reference['git_commit']}:{path}"],
            check=True,
            stdout=subprocess.PIPE,
        )
        actual = "sha256:" + hashlib.sha256(result.stdout).hexdigest()
        assert actual == expected, f"FE atomic Evidence reference drift: {path}"


def generation_digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def build_generation(name: str, *, mixed: bool = False):
    def build(root: Path) -> None:
        (root / "traces").mkdir()
        (root / "screenshots").mkdir()
        (root / "traces" / "row.trace.json").write_text(json.dumps({"generation": name}) + "\n", encoding="utf-8")
        screenshot_generation = "prior" if mixed else name
        (root / "screenshots" / "row.snapshot.json").write_text(json.dumps({"generation": screenshot_generation}) + "\n", encoding="utf-8")
        (root / "results.json").write_text(json.dumps({"status": "passed", "generation": name}) + "\n", encoding="utf-8")
    return build


def validate_generation(root: Path) -> None:
    values = []
    for path in (root / "results.json", root / "traces" / "row.trace.json", root / "screenshots" / "row.snapshot.json"):
        if not path.is_file():
            raise EvidencePublishError(f"partial generation: {path.name}")
        values.append(json.loads(path.read_text(encoding="utf-8"))["generation"])
    if len(set(values)) != 1:
        raise EvidencePublishError("mixed old/new Evidence generation")


def expect_retained(output: Path, before: str, *, build, passed: bool, fault: str | None = None) -> None:
    try:
        publish_directory(output, build, validate_generation, full_run_passed=passed, fault=fault)
    except EvidencePublishError:
        pass
    else:
        raise AssertionError("negative atomic publish unexpectedly succeeded")
    assert generation_digest(output) == before
    assert not (output.parent / ".pattern-scenarios-next").exists()
    assert not (output.parent / ".pattern-scenarios-previous").exists()


def main() -> None:
    verify_fe_reference()
    with tempfile.TemporaryDirectory(prefix="kotlin-atomic-evidence-") as temporary:
        output = Path(temporary) / "pattern-scenarios"
        publish_directory(output, build_generation("prior"), validate_generation, full_run_passed=True)
        prior = generation_digest(output)
        expect_retained(output, prior, build=build_generation("partial"), passed=True, fault="build")
        expect_retained(output, prior, build=build_generation("invalid"), passed=True, fault="validate")
        expect_retained(output, prior, build=build_generation("failed-run"), passed=False)
        expect_retained(output, prior, build=build_generation("mixed", mixed=True), passed=True)
        expect_retained(output, prior, build=build_generation("swap-failure"), passed=True, fault="swap")
        publish_directory(output, build_generation("next"), validate_generation, full_run_passed=True)
        assert generation_digest(output) != prior
        validate_generation(output)
        assert json.loads((output / "results.json").read_text(encoding="utf-8"))["generation"] == "next"
    report = {
        "schema_version": 1,
        "methodology_reference": "baseline/fe-atomic-evidence-reference-v1.json",
        "staging_only_generation": "pass",
        "full_run_publish_only": "pass",
        "failed_run_retains_prior_success": "pass",
        "partial_generation_rejected": "pass",
        "mixed_generation_rejected": "pass",
        "swap_failure_rollback": "pass",
        "verdict": "pass",
    }
    report_path = ROOT / "evidence" / "artifacts" / "atomic-evidence-validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Atomic Evidence Gate: staging-only build, full-pass publish, failed-run retention, mixed-generation rejection, swap rollback = pass")


if __name__ == "__main__":
    main()
