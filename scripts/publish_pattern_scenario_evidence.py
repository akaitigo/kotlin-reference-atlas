#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from atomic_evidence import EvidencePublishError, publish_directory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "pattern-scenarios"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_from(source: Path):
    def build(staging: Path) -> None:
        for item in source.iterdir():
            destination = staging / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
    return build


def validate_generation(staging: Path) -> None:
    report_path = staging / "results.json"
    if not report_path.is_file():
        raise EvidencePublishError("results.json is missing from the staged run")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    counts = report.get("counts", {})
    tests = report.get("tests", [])
    if (
        report.get("status") != "passed"
        or counts.get("total") != len(tests)
        or counts.get("passed") != len(tests)
        or any(counts.get(field) != 0 for field in ("failed", "flaky", "skipped"))
        or not tests
    ):
        raise EvidencePublishError("the complete staged run is not a first-attempt pass set")
    expected_files = {"results.json"}
    for record in tests:
        if record.get("attempts") != 1 or record.get("final_status") != "passed" or record.get("error") is not None:
            raise EvidencePublishError(f"retry/failure record cannot be published: {record.get('id')}")
        oracle = record.get("oracle")
        if not isinstance(oracle, dict) or not oracle:
            raise EvidencePublishError(f"dedicated Oracle is missing: {record.get('id')}")
        for field, directory in (("trace", "traces"), ("screenshot", "screenshots")):
            artifact = record.get(field, {})
            source_name = Path(str(artifact.get("path", ""))).name
            path = staging / directory / source_name
            expected_files.add(path.relative_to(staging).as_posix())
            if not path.is_file() or sha256(path) != artifact.get("digest") or path.stat().st_size != artifact.get("bytes"):
                raise EvidencePublishError(f"staged {field} binding mismatch: {record.get('id')}")
            if field == "trace" and not all(artifact.get(f"{stream}_stream") is True for stream in ("action", "network", "resource")):
                raise EvidencePublishError(f"three-stream Trace contract is missing: {record.get('id')}")
    actual_files = {path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file()}
    if actual_files != expected_files:
        raise EvidencePublishError("partial, stale, or mixed-generation files exist in staging")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("staged_run", type=Path)
    parser.add_argument("--run-status", required=True, choices=["passed", "failed", "timedout", "interrupted"])
    args = parser.parse_args()
    source = args.staged_run.resolve()
    if not source.is_dir():
        raise SystemExit(f"staged run directory does not exist: {source}")
    try:
        published = publish_directory(
            OUTPUT,
            build_from(source),
            validate_generation,
            full_run_passed=args.run_status == "passed",
        )
    except EvidencePublishError as error:
        raise SystemExit(f"Pattern Scenario Evidence was not published; prior success retained: {error}") from error
    if published:
        print("Published one complete Pattern Scenario Evidence generation by staged directory rename")


if __name__ == "__main__":
    main()
