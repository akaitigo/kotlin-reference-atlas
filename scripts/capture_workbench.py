#!/usr/bin/env python3
"""Normalize the executed JVM Workbench into ten retained integrated traces."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reference-systems" / "automation-workbench" / "build" / "test-results" / "test" / "TEST-dev.akaitigo.kotlinatlas.workbench.AutomationWorkbenchTest.xml"
TRACE = ROOT / "reference-systems" / "automation-workbench" / "build" / "evidence" / "runtime-trace.tsv"
OUTPUT = ROOT / "evidence" / "artifacts" / "workbench-jvm-runtime.json"
INTEGRATED_ROOT = ROOT / "evidence" / "scenarios" / "integrated"
REFERENCE_RESULT = ROOT / "evidence" / "scenarios" / "reference-system-results.json"
REFERENCE_MANIFEST = ROOT / "integrations" / "reference-system" / "manifest.json"
SCENARIOS = ["normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility"]
SCENARIO_TARGETS = {
    "normal": ["reference-system.automation-workbench", "semantics.language-core"],
    "boundary": ["semantics.type-system", "security.input-boundaries"],
    "refusal": ["security.input-boundaries"],
    "failure": ["concurrency.structured-cancellation", "quality.failure-debugging"],
    "recovery": ["concurrency.flow-pipelines", "operation.lifecycle-recovery"],
    "migration": ["evolution.compatibility-migration"],
    "operations": ["operation.lifecycle-recovery", "operation.local-evidence"],
    "security": ["security.input-boundaries", "build.toolchain-lock"],
    "performance": ["performance.measurement-harness"],
    "compatibility": ["platform.jvm-js-wasm-runtime", "interop.java-consumer"],
}


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def java_identity() -> str:
    result = subprocess.run(["java", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return (result.stderr or result.stdout).splitlines()[0]


def main() -> None:
    suite = ET.parse(REPORT).getroot()
    counts = {name: int(suite.attrib[name]) for name in ("tests", "failures", "errors", "skipped")}
    if counts != {"tests": 13, "failures": 0, "errors": 0, "skipped": 0}:
        raise SystemExit(f"Workbench JUnit result is not pass: {counts}")
    cases = sorted(case.attrib["name"].removesuffix("()") for case in suite.findall("testcase"))
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "scenario\tvariant\tevents\toutcome\tartifact_digest\thealth":
        raise SystemExit("Workbench Runtime trace header is invalid")
    fields = lines[0].split("\t")
    rows = [dict(zip(fields, line.split("\t"))) for line in lines[1:]]
    if any(len(row) != len(fields) for row in rows) or {item["scenario"] for item in rows} != set(SCENARIOS):
        raise SystemExit("Workbench Runtime trace does not cover the exact ten-scenario set")
    if {item["variant"] for item in rows if item["scenario"] == "boundary"} != {"strict", "normalize"}:
        raise SystemExit("Workbench comparison variants are incomplete")

    source_files = [
        "reference-systems/automation-workbench/src/main/kotlin/dev/akaitigo/kotlinatlas/workbench/AutomationWorkbench.kt",
        "reference-systems/automation-workbench/src/main/kotlin/dev/akaitigo/kotlinatlas/workbench/BoundedDispatcher.kt",
        "reference-systems/automation-workbench/src/main/kotlin/dev/akaitigo/kotlinatlas/workbench/EvidenceScenarioRunner.kt",
    ]
    harness_files = [
        "reference-systems/automation-workbench/src/test/kotlin/dev/akaitigo/kotlinatlas/workbench/AutomationWorkbenchTest.kt",
        "reference-systems/automation-workbench/build.gradle.kts",
        "scripts/capture_workbench.py",
    ]
    source_bindings = [{"path": path, "digest": digest_file(ROOT / path)} for path in source_files]
    harness_bindings = [{"path": path, "digest": digest_file(ROOT / path)} for path in harness_files]
    identity = {
        "compiler": {"name": "Kotlin", "version": "2.4.10", "backend": "JVM IR"},
        "runtime": {"name": "OpenJDK", "identity": java_identity()},
        "platform": {"name": "JVM", "os": platform.system(), "architecture": platform.machine()},
        "build_tool": {"name": "Gradle Wrapper", "version": "9.5.0"},
    }
    traces = []
    for scenario in SCENARIOS:
        scenario_rows = [item for item in rows if item["scenario"] == scenario]
        artifact = {
            "schema_version": 1, "id": f"kotlin-reference-system-trace-{scenario}",
            "atlas_id": "kotlin-reference-atlas", "generated_at": "2026-08-28T00:00:00+09:00",
            "scenario": scenario, "status": "bounded-jvm-runtime-proof", "identity": identity,
            "source_bindings": source_bindings, "harness_bindings": harness_bindings,
            "runtime_rows": scenario_rows, "junit_cases": cases,
            "scope_limit": "This integrated JVM trace is not a per-Surface or per-Behavior proof.",
        }
        path = INTEGRATED_ROOT / f"{scenario}.trace.json"
        write(path, artifact)
        traces.append({
            "scenario": scenario, "path": path.relative_to(ROOT).as_posix(), "digest": digest_file(path),
            "rows": len(scenario_rows), "target_ids": SCENARIO_TARGETS[scenario],
        })
    manifest = {
        "schema_version": 1, "id": "kotlin-automation-workbench-reference-system-v2",
        "status": "bounded-jvm-integration-proof", "runtime": "real-jvm-local",
        "source": source_files, "harness": harness_files,
        "scenarios": [{"id": scenario, "target_ids": SCENARIO_TARGETS[scenario]} for scenario in SCENARIOS],
        "completion_limits": [
            "Integrated success is not reused as proof for every Surface or Behavior.",
            "JVM identity is not substituted for JS, Wasm, or Native runtime identity.",
            "Authority atomic binding requires a recorded human review decision.",
        ],
    }
    write(REFERENCE_MANIFEST, manifest)
    reference = {
        "schema_version": 1, "id": "kotlin-reference-system-results-v2", "status": "bounded-jvm-integration-proof",
        "identity": identity, "trace_source": {"path": TRACE.relative_to(ROOT).as_posix(), "digest": digest_file(TRACE)},
        "scenarios": traces, "summary": {"scenarios": 10, "trace_artifacts": 10, "junit_tests": counts["tests"]},
    }
    write(REFERENCE_RESULT, reference)
    artifact = {
        "schema_version": 2, "suite": "automation-workbench-jvm", "verdict": "pass", "identity": identity,
        "scenarios": {scenario: [item["outcome"] for item in rows if item["scenario"] == scenario] for scenario in SCENARIOS},
        "comparison_variants": ["strict", "normalize"], "runtime_trace": rows, "integrated_traces": traces,
        "tests": cases, "counts": counts,
    }
    write(OUTPUT, artifact)


if __name__ == "__main__":
    main()
