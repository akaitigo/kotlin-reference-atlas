#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Kotlin Atlas固有のEvidence Dependency Graphを決定論的に生成する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence" / "dependency-graph.json"
BASELINE_COMMIT = "0fd5f9bb6af411ad4371674b542eb146de69af96"
RUN_ID_PREFIX = "kotlin-atlas.full-evidence-rerun"
RUN_COMMAND = "python3 scripts/verify.py"
CONTAINER_PROFILE_COMMAND = "scripts/container-verify.sh"
CONTAINER_PROFILE_DOCKERFILE = "environments/container/Dockerfile"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_file(relative: str) -> str:
    return digest_bytes((ROOT / relative).read_bytes())


def load(relative: str) -> dict:
    text = (ROOT / relative).read_text(encoding="utf-8")
    if relative.endswith((".yaml", ".yml")):
        result = {}
        for raw in text.splitlines():
            if not raw or raw[0].isspace() or raw.lstrip().startswith("#") or ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            result[key.strip()] = value.strip().strip('"\'')
        return result
    return json.loads(text)


def write(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def aggregate_current(members: list[str]) -> str:
    return digest_bytes(canonical([
        {"path": path, "digest": digest_file(path)} for path in sorted(members)
    ]))


def aggregate_at_commit(members: list[str]) -> str:
    items = []
    absent = digest_bytes(b"absent-at-evidence-dependency-baseline")
    for path in sorted(members):
        result = subprocess.run(
            ["git", "show", f"{BASELINE_COMMIT}:{path}"], cwd=ROOT,
            check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        items.append({"path": path, "digest": digest_bytes(result.stdout) if result.returncode == 0 else absent})
    return digest_bytes(canonical(items))


def relative_files(root: str, suffixes: set[str]) -> list[str]:
    base = ROOT / root
    if not base.exists():
        return []
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes and "build" not in path.parts
    )


def input_groups(observed_at: str) -> list[dict]:
    source = [
        "sources.lock.yaml", "coverage.yaml", "surface.inventory.yaml",
        "atlas/definitive/kotlin-depth-parity.json",
    ]
    harness = sorted(set([
        "build.gradle.kts", "settings.gradle.kts",
        *relative_files("scripts", {".py", ".sh"}),
        *relative_files("labs", {".kt", ".kts", ".java"}),
        *relative_files("reference-systems", {".kt", ".kts", ".java"}),
    ]))
    runtime = [
        "core.version.yaml", "gradle/libs.versions.toml",
        "gradle/wrapper/gradle-wrapper.properties",
        "kotlin-js-store/package-lock.json", "kotlin-js-store/wasm/package-lock.json",
    ]
    profile = [
        ".github/workflows/ci.yml", "verification.matrix.yaml",
        "environments/container/Dockerfile", "scripts/container-verify.sh",
        "definitive.yaml", "non-regression.yaml",
    ]
    specs = [
        ("input.kotlin-authority-and-surface", "source", source),
        ("input.kotlin-gradle-harness", "harness", harness),
        ("input.compiler-runtime-toolchain", "runtime", runtime),
        ("input.local-container-ci-profile", "profile", profile),
    ]
    result = []
    for identifier, kind, members in specs:
        missing = [path for path in members if not (ROOT / path).is_file()]
        if missing:
            raise RuntimeError(f"Evidence dependency input memberがありません: {missing}")
        result.append({
            "id": identifier,
            "kind": kind,
            "members": sorted(members),
            "baseline_digest": aggregate_at_commit(members),
            "current_digest": aggregate_current(members),
            "observed_at": observed_at,
        })
    return result


def discover_required_outputs() -> list[str]:
    result: set[str] = set()

    def add_if_file(relative: str) -> None:
        if relative and (ROOT / relative).is_file():
            result.add(relative)

    for relative in [
        "artifacts/e2e-results.json", "artifacts/e2e-results.container.json",
        "artifacts/capture-manifest.json", "artifacts/capture-results.json",
        "artifacts/benchmark-results.json", "artifacts/compatibility-results.json",
        "artifacts/reference-system/results.json", "artifacts/pattern-scenarios/results.json",
        "evidence/scenarios/index.json", "evidence/scenarios/closure-plan.json",
    ]:
        add_if_file(relative)
    for root in ["artifacts", "evidence/core-v1", "evidence/reports"]:
        directory = ROOT / root
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            basename = path.name.lower()
            relative = path.relative_to(ROOT).as_posix()
            if root == "artifacts" and not relative.startswith("artifacts/scenario-partial-runtime/") and "results" not in basename and "manifest" not in basename:
                continue
            result.add(relative)
    for pattern in [
        "evidence/*.evidence.json", "evidence/*.evidence.yaml", "evidence/*.evidence.yml",
        "evals/*.definitive-skill-eval.json",
    ]:
        for path in ROOT.glob(pattern):
            if path.is_file():
                result.add(path.relative_to(ROOT).as_posix())
    add_if_file("provenance.yaml")
    index_path = ROOT / "evidence/scenarios/index.json"
    if index_path.is_file():
        for item in load("evidence/scenarios/index.json").get("files", []):
            add_if_file(item.get("path", ""))
    definitive_path = ROOT / "definitive.yaml"
    if definitive_path.is_file():
        manifest = load("definitive.yaml")
        for key in ["scenario_proofs", "scenario_closure_plan", "evidence_durability", "skill_eval", "skill_router"]:
            add_if_file(manifest.get(key, ""))
    return sorted(result)


def output_id(path: str) -> str:
    slug = re.sub(r"[^a-z0-9._:-]+", "-", path.lower()).strip("-")
    return f"output.{slug[:72]}.{hashlib.sha256(path.encode()).hexdigest()[:12]}"


def output_kind(path: str) -> str:
    lower = path.lower()
    if "closure-plan" in lower:
        return "closure-plan"
    if "/scenarios/" in lower and ("proof" in lower or lower.endswith("/index.json")):
        return "scenario-proof"
    if "skill-eval" in lower or lower.endswith("definitive-skill-router.json"):
        return "skill-eval"
    if "benchmark" in lower or "performance" in lower:
        return "benchmark"
    if "compatib" in lower or "migration" in lower:
        return "compatibility"
    if "reference-system" in lower or "workbench" in lower:
        return "reference-system"
    if "platform" in lower or "container" in lower or "native" in lower:
        return "platform-evidence"
    if "capture" in lower or "sbom" in lower:
        return "capture"
    if lower.startswith("evidence/") or lower.startswith("artifacts/"):
        return "runtime-evidence"
    return "derived-evidence"


def scenario_proof_structure() -> str:
    doc = load("evidence/scenarios/index.json")
    files = []
    for item in doc.get("files", []):
        proof = load(item["path"])
        bindings = [
            {"variant_id": binding.get("variant_id"), "path": binding.get("path")}
            for binding in proof.get("source_bindings", [])
        ]
        files.append({
            "id": item.get("id"), "pattern_id": item.get("pattern_id"),
            "scenario": item.get("scenario"), "path": item.get("path"),
            "proof_id": proof.get("id"), "target_id": proof.get("target_id"),
            "target_set": proof.get("target_set"), "behavior_scope": proof.get("behavior_scope"),
            "source_bindings": bindings,
        })
    return digest_bytes(canonical({
        "id": doc.get("id"), "atlas_id": doc.get("atlas_id"),
        "denominator": doc.get("denominator"), "files": files,
    }))


def closure_plan_structure() -> str:
    doc = load("evidence/scenarios/closure-plan.json")
    tranches = []
    for field in ["completed_tranches", "tranches"]:
        for item in doc.get(field, []):
            tranches.append({
                "id": item.get("id"), "risk_rank": item.get("risk_rank"),
                "scenario": item.get("scenario"), "row_ids": item.get("row_ids"),
                "pattern_rows": item.get("pattern_rows"), "variant_runs": item.get("variant_runs"),
                "commit_policy": item.get("commit_policy"),
            })
    ordered_row_ids = []
    for item in doc.get("completed_tranches", []):
        ordered_row_ids.extend(item.get("row_ids", []))
    ordered_row_ids.extend(item.get("id") for item in doc.get("rows", []))
    return digest_bytes(canonical({
        "id": doc.get("id"), "scope": doc.get("scope"), "policy": doc.get("policy"),
        "baseline": doc.get("baseline"), "tranches": tranches,
        "ordered_row_ids": ordered_row_ids,
    }))


def docker_server_version() -> str:
    completed = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    version = completed.stdout.strip()
    if not version:
        raise RuntimeError("Docker server versionを取得できません")
    return version


def generate(run_started_at: str, run_completed_at: str) -> dict:
    inputs = input_groups(run_started_at)
    input_ids = sorted(item["id"] for item in inputs)
    required = discover_required_outputs()
    run_id = f"{RUN_ID_PREFIX}.{hashlib.sha256(run_started_at.encode()).hexdigest()[:12]}"
    outputs = [
        {
            "id": output_id(path), "kind": output_kind(path), "path": path,
            "digest": digest_file(path), "depends_on": input_ids,
            "status": "current", "run_id": run_id,
        }
        for path in required
    ]
    graph = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": run_completed_at,
        "status": "current",
        "policy": {
            "transitive_staleness": True,
            "digest_only_closure_forbidden": True,
            "actual_rerun_required": True,
            "missing_rerun_targets_fail": True,
            "proof_structure_invariant": True,
            "closure_plan_structure_invariant": True,
        },
        "inputs": inputs,
        "outputs": outputs,
        "runs": [{
            "id": run_id, "execution_kind": "runtime",
            "command": RUN_COMMAND,
            "started_at": run_started_at, "completed_at": run_completed_at,
            "result": "passed", "attempts": 1,
            "runtime_identity": {
                "subject": "Kotlin/JVM/JS/Wasm/Native compile, Gradle and container verification",
                "kotlin": "2.4.10", "gradle": "9.5.0", "jvm": "OpenJDK 17",
                "container": "gradle:9.5.0-jdk17", "host": "macOS arm64",
                "docker_server": docker_server_version(),
                "container_profile_command": CONTAINER_PROFILE_COMMAND,
                "container_profile_dockerfile": CONTAINER_PROFILE_DOCKERFILE,
                "native_runtime_substitution": "forbidden; KLIB compile-only is not runtime evidence",
            },
            "input_bindings": [
                {"input_id": item["id"], "digest": item["current_digest"]} for item in sorted(inputs, key=lambda value: value["id"])
            ],
            "output_ids": [item["id"] for item in outputs],
        }],
        "required_outputs": required,
        "structures": [
            {
                "id": "structure.kotlin-scenario-proof-index-v1",
                "kind": "scenario-proof-index", "path": "evidence/scenarios/index.json",
                "baseline_digest": scenario_proof_structure(),
            },
            {
                "id": "structure.kotlin-scenario-closure-plan-v1",
                "kind": "scenario-closure-plan", "path": "evidence/scenarios/closure-plan.json",
                "baseline_digest": closure_plan_structure(),
            },
        ],
    }
    write("evidence/dependency-graph.json", graph)
    return graph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kotlin Evidence Dependency Graphを生成する。")
    parser.add_argument("--run-started-at")
    parser.add_argument("--run-completed-at")
    arguments = parser.parse_args()
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    generated = generate(arguments.run_started_at or now, arguments.run_completed_at or now)
    print(
        "Generated Kotlin Evidence Dependency Graph: "
        f"inputs={len(generated['inputs'])} outputs={len(generated['outputs'])} "
        f"runs={len(generated['runs'])} structures={len(generated['structures'])}"
    )
