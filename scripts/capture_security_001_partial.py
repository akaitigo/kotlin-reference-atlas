#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from atomic_evidence import RETENTION_CONTRACT, publish_directory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "scenario-partial-runtime"
LAB = ROOT / "labs" / "abi-runtime-security"
HARNESS = LAB / "src" / "commonTest" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "ValueClassSecurityTest.kt"
COMMON_SOURCE = LAB / "src" / "commonMain" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "SecureToken.kt"
ABI_CONSUMER = ROOT / "labs" / "abi-compat-consumer"
ABI_HARNESS = ABI_CONSUMER / "src" / "test" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "compat" / "AbiCompatibilityRuntimeTest.kt"
ABI_SOURCES = [
    ROOT / "labs" / "abi-compat-api-v1" / "src" / "main" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "compat" / "SecurePolicy.kt",
    ROOT / "labs" / "abi-compat-api-v2-breaking" / "src" / "main" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "compat" / "SecurePolicy.kt",
    ROOT / "labs" / "abi-compat-api-v2-compatible" / "src" / "main" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "compat" / "SecurePolicy.kt",
    ABI_CONSUMER / "src" / "main" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "compat" / "SecureConsumer.kt",
]
BEHAVIOR = "abi.value-class-boxing-mangling"
SCENARIO = "security"
SURFACE_TESTS = {
    "foundations-mechanics": "foundations mechanics preserves trusted identity at a generic boxing boundary",
    "compatibility-integration": "compatibility integration keeps expect actual value representation executable",
    "performance-capacity-cost": "performance capacity cost boundary remains deterministic under repetition",
}
PROFILES = {
    "kotlin-2.4.10-jvm-openjdk17": {
        "task": ":labs:abi-runtime-security:jvmTest",
        "result": LAB / "build" / "test-results" / "jvmTest" / "TEST-dev.akaitigo.kotlinatlas.abi.ValueClassSecurityTest.xml",
        "binary": LAB / "build" / "libs" / "abi-runtime-security-jvm-0.2.0.jar",
        "platform_source": LAB / "src" / "jvmMain" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "JvmBoundary.kt",
        "runtime": "JVM on OpenJDK 17",
    },
    "kotlin-2.4.10-js-node": {
        "task": ":labs:abi-runtime-security:jsNodeTest",
        "result": LAB / "build" / "test-results" / "jsNodeTest" / "TEST-jsNodeTest.dev.akaitigo.kotlinatlas.abi.ValueClassSecurityTest.xml",
        "binary": LAB / "build" / "compileSync" / "js" / "test" / "testDevelopmentExecutable" / "kotlin" / "kotlin-reference-atlas-labs-abi-runtime-security-test.js",
        "platform_source": LAB / "src" / "jsMain" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "JsBoundary.kt",
        "runtime": "Kotlin/JS IR on Node.js",
    },
    "kotlin-2.4.10-wasm-js-node": {
        "task": ":labs:abi-runtime-security:wasmJsNodeTest",
        "result": LAB / "build" / "test-results" / "wasmJsNodeTest" / "TEST-wasmJsNodeTest.dev.akaitigo.kotlinatlas.abi.ValueClassSecurityTest.xml",
        "binary": LAB / "build" / "compileSync" / "wasmJs" / "test" / "testDevelopmentExecutable" / "kotlin" / "kotlin-reference-atlas-labs-abi-runtime-security-test.wasm",
        "platform_source": LAB / "src" / "wasmJsMain" / "kotlin" / "dev" / "akaitigo" / "kotlinatlas" / "abi" / "WasmBoundary.kt",
        "runtime": "Kotlin/Wasm JS on Node.js",
    },
}
ABI_TASKS = {
    "compatibilityBaselineTest": "CompatibilityBaselineTest",
    "compatibilityBreakingTest": "CompatibilityBreakingTest",
    "migrationBreakingTest": "MigrationBreakingTest",
    "migrationCompatibleTest": "MigrationCompatibleTest",
}
ABI_SURFACE_PHASES = {
    "compatibility-integration": ["compatibilityBaselineTest", "compatibilityBreakingTest"],
    "migration-evolution-deprecation": ["migrationBreakingTest", "migrationCompatibleTest"],
}
ABI_ARTIFACTS = [
    ROOT / "labs" / "abi-compat-api-v1" / "build" / "libs" / "abi-compat-api-v1-0.2.0.jar",
    ROOT / "labs" / "abi-compat-api-v2-breaking" / "build" / "libs" / "abi-compat-api-v2-breaking-0.2.0.jar",
    ROOT / "labs" / "abi-compat-api-v2-compatible" / "build" / "libs" / "abi-compat-api-v2-compatible-0.2.0.jar",
    ABI_CONSUMER / "build" / "libs" / "abi-compat-consumer-0.2.0.jar",
]


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(paths: list[Path]) -> str:
    payload = [
        {"path": path.relative_to(ROOT).as_posix(), "digest": sha256_file(path)}
        for path in sorted(paths)
    ]
    return sha256_bytes(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def binding(path: Path, final_relative: str, *, streams: bool = False) -> dict:
    result = {"path": final_relative, "digest": sha256_file(path), "bytes": path.stat().st_size}
    if streams:
        result |= {"action_stream": True, "network_stream": True, "resource_stream": True}
    return result


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout.strip()


def run_gradle() -> tuple[list[str], str]:
    tasks = [profile["task"] for profile in PROFILES.values()] + [
        f":labs:abi-compat-consumer:{task}" for task in ABI_TASKS
    ]
    command = ["./gradlew", *tasks, "--rerun-tasks", "--no-daemon"]
    environment = os.environ.copy()
    environment.setdefault("GRADLE_USER_HOME", str(ROOT / ".gradle" / "atlas-home"))
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"security-001 partial Runtime suite failed ({result.returncode})\n{result.stdout}")
    return command, result.stdout


def testcases(path: Path) -> list[dict]:
    if not path.is_file():
        raise RuntimeError(f"Runtime result is missing: {path.relative_to(ROOT)}")
    suite = ET.parse(path).getroot()
    if int(suite.attrib.get("failures", "0")) or int(suite.attrib.get("errors", "0")) or int(suite.attrib.get("skipped", "0")):
        raise RuntimeError(f"Runtime result did not fully pass: {path.relative_to(ROOT)}")
    return [dict(item.attrib) for item in suite.findall("testcase")]


def find_case(cases: list[dict], expected: str) -> dict:
    matches = [case for case in cases if case.get("name", "").split("[")[0].removesuffix("()") == expected]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one dedicated Runtime testcase for {expected!r}, found {len(matches)}")
    return matches[0]


def build_generation(staging: Path) -> None:
    command, gradle_output = run_gradle()
    java_identity = command_output(["java", "-version"])
    node_identity = command_output(["node", "--version"])
    gradle_identity = command_output([str(ROOT / "gradlew"), "--version", "--no-daemon"])
    harness_digest = sha256_file(HARNESS)
    records = []
    for variant_id, profile in PROFILES.items():
        result_path, binary_path = profile["result"], profile["binary"]
        cases = testcases(result_path)
        if not binary_path.is_file() or binary_path.stat().st_size == 0:
            raise RuntimeError(f"Runtime compiler artifact is missing: {binary_path.relative_to(ROOT)}")
        source_digest = canonical_digest([COMMON_SOURCE, profile["platform_source"]])
        identity = {
            "compiler": "Kotlin 2.4.10 IR",
            "runtime": profile["runtime"],
            "variant_id": variant_id,
            "gradle": gradle_identity,
            "java": java_identity,
            "node": node_identity,
            "host_os": platform.system(),
            "host_architecture": platform.machine(),
        }
        for surface_id, expected_test in SURFACE_TESTS.items():
            case = find_case(cases, expected_test)
            cell_id = f"cell.{BEHAVIOR}.{surface_id}.{SCENARIO}.{variant_id}"
            safe = cell_id.replace(".", "-")
            trace_path = staging / "traces" / f"{safe}.trace.json"
            artifact_path = staging / "artifacts" / f"{safe}.artifact.json"
            trace = {
                "schema_version": 1,
                "cell_id": cell_id,
                "attempt": 1,
                "retry_count": 0,
                "command": command,
                "task": profile["task"],
                "testcase": case,
                "streams": {
                    "action": ["compile Kotlin target", "launch target runtime", "execute dedicated surface oracle"],
                    "network": ["no application network operation; dependency resolution is repository-locked"],
                    "resource": [f"compiler_artifact={binary_path.relative_to(ROOT).as_posix()}", f"bytes={binary_path.stat().st_size}"],
                },
                "runtime_identity": identity,
                "outcome": "expected",
            }
            artifact = {
                "schema_version": 1,
                "cell_id": cell_id,
                "source_digest": source_digest,
                "harness_digest": harness_digest,
                "test_result": {
                    "path": result_path.relative_to(ROOT).as_posix(),
                    "digest": sha256_file(result_path),
                    "testcase": case,
                },
                "compiler_artifact": {
                    "path": binary_path.relative_to(ROOT).as_posix(),
                    "digest": sha256_file(binary_path),
                    "bytes": binary_path.stat().st_size,
                },
                "oracle": {
                    "kind": "kotlin-value-class-security-boundary",
                    "scenario": SCENARIO,
                    "surface_id": surface_id,
                    "assertion": expected_test,
                    "passed": True,
                },
                "runtime_identity": identity,
            }
            write_json(trace_path, trace)
            write_json(artifact_path, artifact)
            trace_relative = f"artifacts/scenario-partial-runtime/traces/{trace_path.name}"
            artifact_relative = f"artifacts/scenario-partial-runtime/artifacts/{artifact_path.name}"
            records.append({
                "id": cell_id,
                "behavior_id": BEHAVIOR,
                "surface_id": surface_id,
                "scenario": SCENARIO,
                "variant_id": variant_id,
                "source_digest": source_digest,
                "harness_digest": harness_digest,
                "compiler_runtime_platform_identity": identity,
                "oracle": artifact["oracle"],
                "trace": binding(trace_path, trace_relative, streams=True),
                "artifact": binding(artifact_path, artifact_relative),
                "attempts": 1,
                "retries": 0,
                "final_status": "passed",
                "dedicated_to_this_cell": True,
            })
    abi_source_digest = canonical_digest(ABI_SOURCES)
    abi_harness_digest = sha256_file(ABI_HARNESS)
    abi_results = {}
    for task, test_class in ABI_TASKS.items():
        result_path = ABI_CONSUMER / "build" / "test-results" / task / f"TEST-dev.akaitigo.kotlinatlas.abi.compat.{test_class}.xml"
        cases = testcases(result_path)
        if len(cases) != 1:
            raise RuntimeError(f"Expected one dedicated Runtime testcase for {task}, found {len(cases)}")
        abi_results[task] = {"path": result_path, "testcase": cases[0]}
    if any(not path.is_file() or path.stat().st_size == 0 for path in ABI_ARTIFACTS):
        raise RuntimeError("ABI producer/consumer compiler artifact is missing")
    abi_identity = {
        "compiler": "Kotlin 2.4.10 JVM IR",
        "runtime": "JVM binary linkage on OpenJDK 17",
        "variant_id": "kotlin-2.4.10-jvm-openjdk17",
        "gradle": gradle_identity,
        "java": java_identity,
        "host_os": platform.system(),
        "host_architecture": platform.machine(),
    }
    for surface_id, phases in ABI_SURFACE_PHASES.items():
        cell_id = f"cell.abi.source-binary-behavioral.{surface_id}.{SCENARIO}.kotlin-2.4.10-jvm-openjdk17"
        safe = cell_id.replace(".", "-")
        trace_path = staging / "traces" / f"{safe}.trace.json"
        artifact_path = staging / "artifacts" / f"{safe}.artifact.json"
        phase_results = [
            {
                "task": task,
                "path": abi_results[task]["path"].relative_to(ROOT).as_posix(),
                "digest": sha256_file(abi_results[task]["path"]),
                "testcase": abi_results[task]["testcase"],
            }
            for task in phases
        ]
        trace = {
            "schema_version": 1,
            "cell_id": cell_id,
            "attempt": 1,
            "retry_count": 0,
            "command": command,
            "tasks": [f":labs:abi-compat-consumer:{task}" for task in phases],
            "phases": phase_results,
            "streams": {
                "action": ["compile consumer against v1 descriptor", "replace producer JAR without recompiling consumer", "execute JVM linkage oracle"],
                "network": ["no application network operation; dependency resolution is repository-locked"],
                "resource": [f"compiler_artifact={path.relative_to(ROOT).as_posix()}" for path in ABI_ARTIFACTS],
            },
            "runtime_identity": abi_identity,
            "outcome": "expected",
        }
        assertion = (
            "the unchanged v1 consumer runs with v1 and rejects a producer that removed the linked descriptor"
            if surface_id == "compatibility-integration"
            else "the unchanged v1 consumer rejects the breaking producer and recovers with the descriptor-preserving producer"
        )
        artifact = {
            "schema_version": 1,
            "cell_id": cell_id,
            "source_digest": abi_source_digest,
            "harness_digest": abi_harness_digest,
            "test_results": phase_results,
            "compiler_artifacts": [binding(path, path.relative_to(ROOT).as_posix()) for path in ABI_ARTIFACTS],
            "oracle": {
                "kind": "kotlin-jvm-binary-linkage-security",
                "scenario": SCENARIO,
                "surface_id": surface_id,
                "assertion": assertion,
                "passed": True,
            },
            "runtime_identity": abi_identity,
        }
        write_json(trace_path, trace)
        write_json(artifact_path, artifact)
        trace_relative = f"artifacts/scenario-partial-runtime/traces/{trace_path.name}"
        artifact_relative = f"artifacts/scenario-partial-runtime/artifacts/{artifact_path.name}"
        records.append({
            "id": cell_id,
            "behavior_id": "abi.source-binary-behavioral",
            "surface_id": surface_id,
            "scenario": SCENARIO,
            "variant_id": "kotlin-2.4.10-jvm-openjdk17",
            "source_digest": abi_source_digest,
            "harness_digest": abi_harness_digest,
            "compiler_runtime_platform_identity": abi_identity,
            "oracle": artifact["oracle"],
            "trace": binding(trace_path, trace_relative, streams=True),
            "artifact": binding(artifact_path, artifact_relative),
            "attempts": 1,
            "retries": 0,
            "final_status": "passed",
            "dedicated_to_this_cell": True,
        })
    report = {
        "schema_version": 1,
        "id": "kotlin-security-001-partial-runtime-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "passed",
        "command": " ".join(command),
        "profile": "real-kotlin-jvm-js-wasm-runtime",
        "retention_contract": RETENTION_CONTRACT,
        "source_digest": canonical_digest([COMMON_SOURCE, *[profile["platform_source"] for profile in PROFILES.values()], *ABI_SOURCES]),
        "harness_digest": canonical_digest([HARNESS, ABI_HARNESS]),
        "counts": {"cells": len(records), "passed": len(records), "failed": 0, "variants": len(PROFILES), "surfaces": len(SURFACE_TESTS) + len(ABI_SURFACE_PHASES), "behaviors": 2},
        "execution": {"attempts": 1, "retries": 0, "full_requested_profile_passed": True},
        "completion_limits": [
            "security-001 is not complete: Native runtime cells require a working Xcode toolchain and remain explicit gaps.",
            "JS and Wasm cells for abi.source-binary-behavioral remain explicit gaps.",
            "This generation closes only the exact cell records listed in this report.",
        ],
        "records": records,
        "gradle_output_digest": sha256_bytes(gradle_output.encode()),
    }
    write_json(staging / "results.json", report)


def validate_generation(staging: Path) -> None:
    report = json.loads((staging / "results.json").read_text(encoding="utf-8"))
    records = report.get("records", [])
    expected_ids = {
        f"cell.{BEHAVIOR}.{surface}.{SCENARIO}.{variant}"
        for surface in SURFACE_TESTS
        for variant in PROFILES
    }
    expected_ids |= {
        f"cell.abi.source-binary-behavioral.{surface}.{SCENARIO}.kotlin-2.4.10-jvm-openjdk17"
        for surface in ABI_SURFACE_PHASES
    }
    if report.get("status") != "passed" or {record.get("id") for record in records} != expected_ids:
        raise RuntimeError("partial Runtime report does not contain the exact requested cell denominator")
    seen_paths = set()
    for record in records:
        if record.get("attempts") != 1 or record.get("retries") != 0 or record.get("final_status") != "passed":
            raise RuntimeError(f"first-attempt/retry-zero contract failed: {record.get('id')}")
        for field in ("trace", "artifact"):
            item = record[field]
            relative_inside = Path(item["path"]).relative_to("artifacts/scenario-partial-runtime")
            path = staging / relative_inside
            if item["path"] in seen_paths or not path.is_file() or sha256_file(path) != item["digest"] or path.stat().st_size != item["bytes"]:
                raise RuntimeError(f"dedicated Artifact binding failed: {record.get('id')}:{field}")
            seen_paths.add(item["path"])


def main() -> None:
    publish_directory(OUTPUT, build_generation, validate_generation, full_run_passed=True)
    report = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    print(f"security-001 partial Runtime Evidence: cells={report['counts']['cells']} variants={report['counts']['variants']} status={report['status']}")


if __name__ == "__main__":
    main()
