#!/usr/bin/env python3
"""Normalize the executed Workbench JUnit result into retained evidence."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reference-systems" / "automation-workbench" / "build" / "test-results" / "test" / "TEST-dev.akaitigo.kotlinatlas.workbench.AutomationWorkbenchTest.xml"
TRACE = ROOT / "reference-systems" / "automation-workbench" / "build" / "evidence" / "runtime-trace.tsv"
OUTPUT = ROOT / "evidence" / "artifacts" / "workbench-jvm-runtime.json"


def main() -> None:
    suite = ET.parse(REPORT).getroot()
    tests = int(suite.attrib["tests"])
    failures = int(suite.attrib["failures"])
    errors = int(suite.attrib["errors"])
    skipped = int(suite.attrib["skipped"])
    if (tests, failures, errors, skipped) != (8, 0, 0, 0):
        raise SystemExit(f"Workbench JUnit result is not pass: {(tests, failures, errors, skipped)}")
    cases = sorted(case.attrib["name"].removesuffix("()") for case in suite.findall("testcase"))
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "scenario\tvariant\tevents\toutcome\tartifact_digest\thealth":
        raise SystemExit("Workbench Runtime trace header is invalid")
    fields = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    if any(len(row) != len(fields) for row in rows):
        raise SystemExit("Workbench Runtime trace row is invalid")
    trace = [dict(zip(fields, row)) for row in rows]
    if len(trace) != 8 or {item["scenario"] for item in trace} != {"normal", "boundary", "rejection", "failure", "recovery"}:
        raise SystemExit("Workbench Runtime trace does not cover all required scenarios")
    if {item["variant"] for item in trace if item["scenario"] == "boundary"} != {"strict", "normalize"}:
        raise SystemExit("Workbench Runtime trace comparison variants are incomplete")
    artifact = {
        "schema_version": 1,
        "suite": "automation-workbench-jvm",
        "verdict": "pass",
        "runtime": {
            "platform": "jvm",
            "identity": "Homebrew OpenJDK 17.0.17+0 aarch64",
            "kotlin": "2.4.10",
            "kotlinx_coroutines": "1.11.0",
        },
        "scenarios": {
            "normal": ["normal execution emits context attempt and immutable artifact"],
            "boundary": ["boundary policy compares strict rejection with normalization"],
            "rejection": ["invalid identifier and attempt limit are rejected before execution", "bounded dispatcher exposes backpressure and closed recovery path"],
            "failure": ["permanent failure is categorized and observable", "cancellation is not converted into failure and active gauge recovers"],
            "recovery": ["transient failure recovers within bounded retry budget", "duplicate execution returns stored artifact without rerunning step"],
        },
        "comparison_variants": ["strict", "normalize"],
        "runtime_trace": trace,
        "tests": cases,
        "counts": {"tests": tests, "failures": failures, "errors": errors, "skipped": skipped},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
