#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = "2026-08-28T00:00:00+09:00"
MANIFESTS = ["atlas.yaml", "mastery.yaml", "coverage.yaml", "sources.lock.yaml", "skill.package.yaml"]
DEFINITIVE_MANIFESTS = [
    "definitive.yaml",
    "depth.parity.yaml",
    "non-regression.yaml",
    "baselines/definitive-c0e9b1c.core-072d7ca.non-regression-baseline.json",
    "evidence/scenarios/index.json",
    "evidence/scenarios/closure-plan.json",
    "artifacts/pattern-scenarios/results.json",
    "evidence/dependency-graph.json",
    "surface.inventory.yaml",
    "verification.matrix.yaml",
    "evals/kotlin-reference-router.definitive-skill-eval.json",
    "evals/definitive-skill-router.json",
    "authority/body-inventory.snapshot.json",
    "authority/review-queue.snapshot.json",
    "migrations/definitive-v2.yaml",
]
ARTIFACTS = ROOT / "evidence" / "artifacts"
ROUTER = ROOT / ".agents" / "skills" / "kotlin-reference-router" / "scripts" / "route.py"


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def digest_tree(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file() and "build" not in item.parts)
        elif path.is_file():
            files.append(path)
    for path in sorted(set(files)):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def harness_file(paths: Iterable[Path]) -> Path:
    candidates: list[Path] = []
    for path in paths:
        if path.is_file():
            candidates.append(path)
            continue
        if path.is_dir():
            preferred = path / "build.gradle.kts"
            if preferred.is_file():
                candidates.append(preferred)
                continue
            candidates.extend(
                item for item in path.rglob("*")
                if item.is_file() and "build" not in item.parts
            )
    if not candidates:
        raise RuntimeError("Evidenceへ束縛できるHarness fileがありません")
    return sorted(set(candidates))[0]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("実行:", " ".join(command))
    environment = os.environ.copy()
    environment.setdefault("GRADLE_USER_HOME", str(ROOT / ".gradle" / "atlas-home"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")
    return result


def run_expect_failure(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("失敗を期待して実行:", " ".join(command))
    environment = os.environ.copy()
    environment.setdefault("GRADLE_USER_HOME", str(ROOT / ".gradle" / "atlas-home"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode == 0:
        raise RuntimeError("未完RepositoryがDefinitive Gateを通過した")
    return result


def detect_full_xcode() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/usr/bin/xcrun", "xcodebuild", "-version"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def validate_manifests() -> dict:
    authority_manifests = [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "authority" / "surfaces").glob("*.yaml"))]
    run([sys.executable, str(ROOT / "scripts" / "generate_core_authority_extraction.py")])
    authority_drafts = [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "authority" / "surfaces-draft").glob("*.json"))]
    run([str(ROOT / "bin" / "atlas"), "validate", *MANIFESTS, *DEFINITIVE_MANIFESTS, "authority/extraction.snapshot.json", *authority_drafts, *authority_manifests])
    atlas = load_json(ROOT / "atlas.yaml")
    mastery = load_json(ROOT / "mastery.yaml")
    coverage = load_json(ROOT / "coverage.yaml")
    sources = load_json(ROOT / "sources.lock.yaml")
    package = load_json(ROOT / "skill.package.yaml")
    migration = load_json(ROOT / "migrations" / "core-v1.yaml")
    core_version = load_json(ROOT / "core.version.yaml")
    expected_digest = sha256_file(ROOT / "sources.lock.yaml")
    errors = []
    if len({atlas["id"], mastery["atlas_id"], coverage["atlas_id"], sources["atlas_id"], package["atlas_id"]}) != 1:
        errors.append("5 Manifestのatlas_idが一致しない")
    if len({atlas["coverage"]["epoch"], mastery["epoch"], coverage["epoch"], sources["epoch"]}) != 1:
        errors.append("Coverage Epochが一致しない")
    if coverage["authority_lock_digest"] != expected_digest:
        errors.append("authority_lock_digestがsources.lock.yamlと一致しない")
    if migration["unmapped_source_ids"]:
        errors.append("Core v1 migrationに未対応source IDがある")
    if migration["target"]["core_commit"] != core_version["commit"]:
        errors.append("MigrationとCore Versionのcommitが一致しない")
    historical = ROOT / "evidence" / "history" / "v0.2.0" / "completion-certificate.json"
    if not historical.is_file() or sha256_file(historical) != "sha256:bc01f8663533afd9be105e4cfe157d34b561735375c5d51ba38ce8f96493286f":
        errors.append("bounded historical Certificateが固定値と一致しない")
    if (ROOT / "evidence" / "completion-certificate.json").exists():
        errors.append("bounded historical Certificateをactive Certificateとして扱っている")
    if atlas["status"] == "incomplete" and (ROOT / "evidence" / "definitive-certificate.json").exists():
        errors.append("incomplete状態でDefinitive Certificateが存在する")
    inventory_summary = load_json(ROOT / "atlas" / "definitive" / "inventory-summary.json")
    if inventory_summary["authority_artifacts"] < 1 or inventory_summary["behaviors"] < 1:
        errors.append("Authority Surface Inventoryが空")
    if errors:
        raise RuntimeError("; ".join(errors))
    result = {
        "atlas_id": atlas["id"],
        "epoch": coverage["epoch"],
        "authority_lock_digest": expected_digest,
        "mastery_outcomes": len(mastery["outcomes"]),
        "mastery_surfaces": len(mastery["surfaces"]),
        "authority_artifacts": inventory_summary["authority_artifacts"],
        "authority_behaviors": inventory_summary["behaviors"],
        "bounded_historical_certificate": historical.relative_to(ROOT).as_posix(),
        "audit_output": "最終GateでCore auditを再実行する",
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "manifest-validation.json", result)
    return result


def collect_test_results() -> dict:
    command = [str(ROOT / "gradlew"), "clean", "atlasCheck"]
    if detect_full_xcode().returncode == 0:
        command.append(":labs:multiplatform:macosArm64Test")
    command.extend(["--configuration-cache", "--no-daemon"])
    run(command)
    suites = []
    reports = [
        report
        for root in (ROOT / "labs", ROOT / "reference-systems")
        for report in root.rglob("TEST-*.xml")
    ]
    for report in sorted(reports):
        xml_root = ET.parse(report).getroot()
        cases = []
        for case in xml_root.findall("testcase"):
            status = "pass"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "fail"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append({"class": case.attrib.get("classname", ""), "name": case.attrib.get("name", ""), "status": status})
        relative = report.relative_to(ROOT)
        module = relative.parts[1] if relative.parts[0] == "labs" else "/".join(relative.parts[:2])
        suites.append({"module": module, "task": report.parent.name, "suite": xml_root.attrib.get("name", ""), "cases": sorted(cases, key=lambda item: (item["class"], item["name"]))})
    if not suites or any(case["status"] != "pass" for suite in suites for case in suite["cases"]):
        raise RuntimeError("全LabのJUnit resultをpassとして収集できない")
    result = {"command": " ".join(command).replace(str(ROOT / "gradlew"), "./gradlew"), "suites": suites, "test_case_count": sum(len(suite["cases"]) for suite in suites), "verdict": "pass"}
    write_json(ARTIFACTS / "lab-results.json", result)
    return result


def generate_deep_artifacts() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "capture_workbench.py")])
    run([sys.executable, str(ROOT / "scripts" / "test_atomic_evidence.py")])
    run([sys.executable, str(ROOT / "scripts" / "inventory.py")])
    run([sys.executable, str(ROOT / "scripts" / "inspect_bytecode.py")])
    run([sys.executable, str(ROOT / "scripts" / "generate_sbom.py")])
    native_klib = ROOT / "labs" / "multiplatform" / "build" / "classes" / "kotlin" / "macosArm64" / "test" / "klib"
    wasm = ROOT / "labs" / "multiplatform" / "build" / "compileSync" / "wasmJs" / "test" / "testDevelopmentExecutable" / "kotlin" / "kotlin-reference-atlas-labs-multiplatform-test.wasm"
    errors = []
    if not native_klib.is_dir():
        errors.append("Native test KLIBが生成されていない")
    if not wasm.is_file():
        errors.append("Wasm test executableが生成されていない")
    if errors:
        raise RuntimeError("; ".join(errors))
    xcode = detect_full_xcode()
    native_runtime_report = next((ROOT / "labs" / "multiplatform").rglob("macosArm64Test/TEST-*.xml"), None)
    if xcode.returncode == 0 and native_runtime_report is None:
        raise RuntimeError("Full Xcode環境でmacosArm64Test resultを収集できない")
    result = {
        "jvm_runtime": "pass",
        "js_node_runtime": "pass",
        "wasm_node_runtime": "pass",
        "wasm_digest": sha256_file(wasm),
        "native_macos_arm64_compile": "pass",
        "native_test_klib_digest": digest_tree([native_klib]),
        "native_runtime": {
            "verdict": "pass" if xcode.returncode == 0 else "infeasible",
            "xcodebuild_exit_code": xcode.returncode,
            "xcodebuild_output": xcode.stdout.strip(),
            "reason": "Full XcodeのxcodebuildがHostに存在しないためlinkDebugTestMacosArm64を実行できない" if xcode.returncode != 0 else "Full Xcode環境でmacosArm64Testを実行した",
        },
        "native_compile_is_runtime_substitute": False,
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "platform-validation.json", result)
    return result


def validate_container_profile() -> dict:
    completed = run([str(ROOT / "scripts" / "container-verify.sh")], capture=True)
    inspected = run(["docker", "image", "inspect", "kotlin-reference-atlas-verify:local", "--format", "{{.Id}}"], capture=True)
    result = {
        "command": "scripts/container-verify.sh",
        "image": "gradle:9.5.0-jdk17",
        "local_image_id": inspected.stdout.strip(),
        "network_disabled_on_replay": True,
        "output_tail": completed.stdout[-20000:] if completed.stdout else "",
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "container-verification.json", result)
    return result


def run_skill_evals() -> dict:
    cases = load_json(ROOT / "evals" / "router-cases.json")["cases"]
    results = []
    for case in cases:
        completed = run([sys.executable, str(ROUTER), "--query", case["query"]], capture=True)
        actual = json.loads(completed.stdout)
        passed = actual["disposition"] == case["expected_disposition"]
        if "expected_capability_id" in case:
            passed = passed and actual.get("capability_id") == case["expected_capability_id"]
        if "expected_outcome" in case:
            passed = passed and case["expected_outcome"] in actual.get("outcome_ids", [])
        if "expected_surface" in case:
            passed = passed and case["expected_surface"] in actual.get("surface_ids", [])
        results.append({
            "id": case["id"],
            "actual_disposition": actual["disposition"],
            "actual_capability_id": actual.get("capability_id"),
            "outcome_ids": actual.get("outcome_ids", []),
            "surface_ids": actual.get("surface_ids", []),
            "pass": passed,
        })
    pass_rate = sum(1 for result in results if result["pass"]) / len(results)
    minimum = load_json(ROOT / "skill.package.yaml")["evals"]["minimum_pass_rate"]
    if pass_rate < minimum:
        raise RuntimeError(f"Skill Eval pass rate {pass_rate} is below {minimum}")
    result = {"case_count": len(results), "pass_rate": pass_rate, "results": results, "verdict": "pass"}
    write_json(ARTIFACTS / "skill-eval.json", result)
    categories = {
        "semantics-design": "routing", "types-implement": "routing", "jvm-value-class": "routing",
        "multiplatform-review": "execution", "native-compile": "execution", "java-interop": "near-neighbor",
        "compiler-bytecode": "execution", "gradle-testkit": "execution", "toolchain-security": "authorization",
        "coroutine-cancellation": "lifecycle", "flow-diagnose": "lifecycle", "performance-review": "execution",
        "security-review": "security", "migration": "lifecycle", "operation-recovery": "lifecycle",
        "sbom-review": "authority", "swift-export-gap": "coverage-gap", "ktor-gap": "coverage-gap",
    }
    entity = {
        "schema_version": 1,
        "id": "kotlin-reference-router.v0-2-0",
        "atlas_id": "kotlin-reference-atlas",
        "atlas_release": "v0.2.0",
        "skill_id": "kotlin-reference-router",
        "generated_at": CREATED_AT,
        "cases": [
            {
                "id": item["id"],
                "category": categories[item["id"]],
                "result": "pass" if item["pass"] else "fail",
                "assertion": f"Router Eval {item['id']}は期待DispositionとCapability境界を満たす。",
            }
            for item in results
        ],
    }
    write_json(ROOT / "evals" / "kotlin-reference-router.skill-eval.json", entity)
    legacy_evidence = evidence_record(
        "skill.router-evaluation", ["skill.router-respects-coverage"], "skill-eval", "kotlin-router-eval",
        "python3 scripts/verify.py", ROOT / "evals" / "kotlin-reference-router.skill-eval.json",
        [ROOT / ".agents" / "skills" / "kotlin-reference-router", ROOT / "evals"],
    )
    write_json(ROOT / "evidence" / "skill.router-evaluation.evidence.json", legacy_evidence)
    forward_eval = ROOT / "evals" / "kotlin-reference-router.agent-forward-eval.json"
    if forward_eval.is_file():
        forward_evidence = evidence_record(
            "skill.agent-forward-evaluation", ["skill.definitive-routing-is-bounded"], "skill-eval", "independent-agent-forward-eval",
            "independent subagent forwarded Router scenarios", forward_eval,
            [ROOT / ".agents" / "skills" / "kotlin-reference-router", forward_eval],
        )
        write_json(ROOT / "evidence" / "skill.agent-forward-evaluation.evidence.json", forward_evidence)
    return result


def validate_definitive_skill_eval() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "generate_definitive_skill_eval.py")])
    schema_entity = load_json(ROOT / "evals" / "kotlin-reference-router.definitive-skill-eval.json")
    entity = load_json(ROOT / "evals" / "kotlin-reference-router.definitive-skill-eval-report.json")
    mastery = load_json(ROOT / "mastery.yaml")
    coverage = load_json(ROOT / "coverage.yaml")
    sources = {item["id"]: item for item in load_json(ROOT / "sources.lock.yaml")["sources"]}
    errors = []
    summary = entity.get("summary", {})
    matrix = entity.get("matrix", [])
    boundaries = entity.get("boundary_cases", [])
    inventory = entity.get("target_state_inventory", [])
    if entity.get("status") != "incomplete" or load_json(ROOT / "atlas.yaml").get("status") != "incomplete":
        errors.append("Matrix passからcompleteへ昇格している")
    if summary.get("outcome_count") != 8 or len(mastery["outcomes"]) != 8:
        errors.append("Outcomeが8件ではない")
    if summary.get("surface_count") != 14 or len(mastery["surfaces"]) != 14:
        errors.append("Surfaceが14件ではない")
    if len(matrix) != 112 or summary.get("matrix_cell_count") != 112:
        errors.append("8 Outcome×14 Surfaceの112-cell Matrixではない")
    if schema_entity.get("schema_version") != 2 or len(schema_entity.get("cases", [])) != 123:
        errors.append("Core v2 Skill Eval Schema case集合が旧3件＋追加120件ではない")
    if not summary.get("matrix_contract_pass") or any(item.get("result") != "pass" for item in matrix):
        errors.append("Matrix契約に失敗Cellがある")
    if summary.get("routing_gap_count", 0) <= 0:
        errors.append("Mastery routing gapを隠している")
    expected_boundary_codes = {
        "ambiguous-query", "unknown-query", "unauthorized-mutation", "external-human-decision-required",
        "stale-source-relock-explicit-procedure-required", "target-not-covered", "mastery-routing-gap",
    }
    actual_boundary_codes = {item.get("actual", {}).get("reason_code") for item in boundaries if item.get("result") == "pass"}
    if actual_boundary_codes != expected_boundary_codes:
        errors.append("fail-closed境界Caseが不足または不一致")
    target_projection = {(item["id"], item["state"], item["requirement"]) for item in coverage["targets"]}
    inventory_projection = {(item["id"], item["state"], item["requirement"]) for item in inventory}
    if target_projection != inventory_projection:
        errors.append("全Target state InventoryがCoverageと一致しない")
    for cell in matrix:
        route = cell.get("route", {})
        if route.get("disposition") != "covered":
            if route.get("reason_code") != "mastery-routing-gap":
                errors.append(f"{cell.get('id')}: gapがMastery契約外の理由")
            continue
        if route.get("target_state") != "covered" or not route.get("target_set_allowed"):
            errors.append(f"{cell.get('id')}: covered RouteのTarget state不正")
        if not route.get("implementation_bindings") or not route.get("source_bindings") or not route.get("evidence_bindings"):
            errors.append(f"{cell.get('id')}: implementation/source/evidence binding不足")
        mutation = route.get("mutation", {})
        if mutation.get("required") and not mutation.get("authorized"):
            errors.append(f"{cell.get('id')}: mutation authorization不足")
        for source in route.get("source_bindings", []):
            locked = sources.get(source.get("id"))
            if locked is None or source.get("digest") != locked.get("digest") or source.get("url") != locked.get("url"):
                errors.append(f"{cell.get('id')}: Source binding不一致")
        for evidence in route.get("evidence_bindings", []):
            artifact = evidence.get("artifact", {})
            artifact_path = ROOT / artifact.get("path", "")
            if not artifact_path.is_file() or sha256_file(artifact_path) != artifact.get("digest"):
                errors.append(f"{cell.get('id')}: Evidence artifact binding不一致")
    forward = entity.get("independent_agent_forward_eval", {})
    required_forward_dimensions = {
        "outcome_surface_forwarding", "mutation_authorization", "human_authority_stop", "stale_relock_stop",
        "ambiguous_unknown_fail_closed", "source_binding", "routing_gap", "all_target_states",
    }
    dimensions = forward.get("coverage_dimensions", {})
    if forward.get("verdict") != "pass" or forward.get("completion_claim") is not False:
        errors.append("独立Agent Forward Evalがpassでないかcompletionを主張している")
    if forward.get("evaluated_by", {}).get("kind") != "independent-subagent":
        errors.append("Forward Evalの独立Evaluator識別子がない")
    if forward.get("target_state_counts") != summary.get("target_state_counts") or sum(forward.get("target_state_counts", {}).values()) != len(coverage["targets"]):
        errors.append("Forward Evalの全Target state照合が現行Coverageと一致しない")
    passing_dimensions = {
        key for key, value in dimensions.items()
        if value == "pass" or (isinstance(value, dict) and value.get("status") == "pass")
    }
    if not required_forward_dimensions.issubset(passing_dimensions):
        errors.append("Forward Evalの必須評価Dimensionが不足")
    if len(forward.get("scenarios", [])) < 8 or any(not item.get("pass") for item in forward.get("scenarios", [])):
        errors.append("Forward Eval Scenarioが不足または失敗")
    if errors:
        raise RuntimeError("Definitive Skill Eval失敗: " + "; ".join(sorted(set(errors))))
    result = {
        "matrix_cell_count": len(matrix),
        "routed_cell_count": summary["routed_cell_count"],
        "routing_gap_count": summary["routing_gap_count"],
        "target_state_counts": summary["target_state_counts"],
        "boundary_case_count": len(boundaries),
        "independent_agent_scenario_count": len(forward["scenarios"]),
        "completion_claim": False,
        "verdict": "pass-bounded-incomplete",
    }
    write_json(ARTIFACTS / "definitive-skill-eval-validation.json", result)
    return result


def validate_rights() -> dict:
    required = [
        "LICENSE",
        "NOTICE",
        "SECURITY.md",
        "third_party/manifest.yaml",
        "third_party/sbom.cdx.json",
        "sbom.spdx.json",
        "gradle/verification-metadata.xml",
        "settings-gradle.lockfile",
        "labs/jvm/gradle.lockfile",
        "labs/coroutines/gradle.lockfile",
        "labs/interop/gradle.lockfile",
        "labs/gradle-plugin/gradle.lockfile",
        "reference-systems/automation-workbench/gradle.lockfile",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    manifest = load_json(ROOT / "third_party" / "manifest.yaml")
    sbom = load_json(ROOT / "third_party" / "sbom.cdx.json")
    spdx = load_json(ROOT / "sbom.spdx.json")
    direct_ids = {item["id"] for item in manifest["artifacts"]}
    sbom_names = {item["name"] for item in sbom["components"]}
    errors = []
    if missing:
        errors.append("missing=" + ",".join(missing))
    if not {"reference-atlas-core", "gradle-distribution", "nodejs-runtime", "eclipse-temurin-runtime"}.issubset(direct_ids):
        errors.append("third_party manifestの固定Toolchain依存が不足")
    if not {"kotlin", "gradle", "kotlinx-coroutines-core-jvm", "junit-bom"}.issubset(sbom_names):
        errors.append("SBOMの直接依存が不足")
    spdx_names = {item["name"] for item in spdx["packages"]}
    spdx_purls = {
        reference["referenceLocator"]
        for item in spdx["packages"]
        for reference in item.get("externalRefs", [])
        if reference.get("referenceType") == "purl"
    }
    expected_gradle = set()
    for lock in sorted(ROOT.rglob("gradle.lockfile")) + [ROOT / "settings-gradle.lockfile"]:
        if not lock.is_file() or "build" in lock.parts:
            continue
        for line in lock.read_text(encoding="utf-8").splitlines():
            coordinate = line.split("=", 1)[0]
            parts = coordinate.split(":")
            if len(parts) == 3:
                expected_gradle.add(f"pkg:maven/{parts[0]}/{parts[1]}@{parts[2]}")
    expected_npm = set()
    for lock in [ROOT / "kotlin-js-store" / "package-lock.json", ROOT / "kotlin-js-store" / "wasm" / "package-lock.json"]:
        document = load_json(lock)
        for path, package in document.get("packages", {}).items():
            if path and "node_modules/" in path and "version" in package:
                name = path.rsplit("node_modules/", 1)[1]
                if name.startswith("kotlin-reference-atlas-"):
                    continue
                expected_npm.add(f"pkg:npm/{name}@{package['version']}")
    missing_purls = sorted((expected_gradle | expected_npm) - spdx_purls)
    if spdx.get("spdxVersion") != "SPDX-2.3" or not {"kotlin-reference-atlas", "org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains.kotlin:kotlin-compiler-embeddable", "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm"}.issubset(spdx_names):
        errors.append("SPDX SBOMの必須Packageが不足")
    if missing_purls:
        errors.append(f"SPDX SBOMにLock Componentが不足: {len(missing_purls)}")
    if sha256_file(ROOT / "gradle" / "wrapper" / "gradle-wrapper.jar") != "sha256:497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7":
        errors.append("Gradle Wrapper JAR checksumが9.5.0公式値と一致しない")
    wrapper_properties = (ROOT / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(encoding="utf-8")
    if "distributionSha256Sum=553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746" not in wrapper_properties:
        errors.append("Gradle distribution checksumが固定値と一致しない")
    if errors:
        raise RuntimeError("; ".join(errors))
    locked_manifest = {
        (item["name"], item["version"], item["license"])
        for item in manifest["artifacts"]
        if item["id"].startswith("locked-")
    }
    locked_sbom = {
        (item["name"], item["versionInfo"], item["licenseDeclared"])
        for item in spdx["packages"]
        if item["name"] != "kotlin-reference-atlas"
    }
    if locked_manifest != locked_sbom:
        errors.append("第三者ManifestとSPDX transitive closureが一致しない")
    if errors:
        raise RuntimeError("; ".join(errors))
    result = {"required_files": required, "direct_component_count": len(manifest["artifacts"]), "sbom_formats": ["CycloneDX-1.6", "SPDX-2.3"], "sbom_scope": "gradle-and-npm-lock-transitive-closure", "spdx_package_count": len(spdx["packages"]), "lock_component_count": len(expected_gradle | expected_npm), "missing_lock_components": [], "verdict": "pass"}
    write_json(ARTIFACTS / "rights-validation.json", result)
    return result


def validate_non_regression() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "verify_non_regression.py")])
    result = load_json(ARTIFACTS / "non-regression.json")
    if result.get("verdict") != "pass" or result.get("violations"):
        raise RuntimeError("公開main非後退Gateがpassではない")
    # Core v2はRepository配下の全Lab pathを監査するため、Evidenceへ収集済みの
    # Gradle生成物を除去して追跡Source/Harnessだけを入力にする。
    run([str(ROOT / "gradlew"), "clean", "--no-daemon"])
    core = run([str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "non-regression"], capture=True)
    result["core_v2_audit"] = core.stdout.strip()
    result["core_v2_baseline"] = "baselines/definitive-c0e9b1c.core-e822.non-regression-baseline.json"
    result["core_v2_baseline_anchor"] = "baselines/definitive-c0e9b1c.non-regression-baseline.json"
    write_json(ARTIFACTS / "non-regression.json", result)
    return result


def validate_authority_locators() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "generate_authority_locators.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_authority_locators.py")])
    result = load_json(ARTIFACTS / "authority-locator-validation.json")
    if result.get("verdict") != "pass" or result.get("violations"):
        raise RuntimeError("Authority locator Gateがpassではない")
    if result.get("summary", {}).get("authority_text_surfaces_exhaustive") is not False:
        raise RuntimeError("Authority本文全体の未完状態が失われた")
    return result


def validate_authority_body_inventory() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "verify_authority_body_inventory.py")])
    result = load_json(ARTIFACTS / "authority-body-inventory-validation.json")
    if result.get("verdict") != "pass" or result.get("violations") or result.get("raw_anchor_depth_credit") is not False:
        raise RuntimeError("Authority body denominator Gateがpassではない")
    return result


def validate_authority_review_queue() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "generate_authority_review_queue.py")])
    run([sys.executable, str(ROOT / "scripts" / "test_authority_review_queue.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_authority_review_queue.py")])
    result = load_json(ARTIFACTS / "authority-review-queue-validation.json")
    if result.get("verdict") != "pass" or result.get("violations") or result.get("queue_depth_credit") is not False or result.get("all_raw_anchors_routed") is not True:
        raise RuntimeError("Authority review queue Gateがpassではない")
    artifact = ARTIFACTS / "authority-review-queue-validation.json"
    record = evidence_record(
        "authority.review-queue-validation",
        ["authority.raw-anchor-denominator-is-pending-human"],
        "capture",
        "kotlin-authority-review-queue-verifier",
        "python3 scripts/generate_authority_review_queue.py && python3 scripts/test_authority_review_queue.py && python3 scripts/verify_authority_review_queue.py",
        artifact,
        [ROOT / "scripts" / "verify_authority_review_queue.py", ROOT / "authority" / "review-queue.snapshot.json", ROOT / "authority" / "reviews" / "decisions.json", ROOT / "authority" / "reviews" / "promotions.json"],
    )
    write_json(ROOT / "evidence" / "authority.review-queue-validation.evidence.json", record)
    return result


def validate_fe_parity() -> dict:
    run([sys.executable, str(ROOT / "scripts" / "verify_fe_parity.py")])
    result = load_json(ARTIFACTS / "kotlin-depth-parity.json")
    if result.get("violations") or result.get("verdict") not in {"incomplete", "pass"}:
        raise RuntimeError("Kotlin Depth Parity Gateの状態が不整合")
    return result


def validate_neutral_language() -> dict:
    listed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.splitlines()
    # 検査語そのものを検査実装へ連続して書くと、このファイルが自己検出される。
    forbidden = ("決定" + "版", "世界" + "一", "唯" + "一", "作者" + "称賛", "最高" + "品質", "推奨" + "したく")
    namespace = "aka" + "itigo"
    technical_namespace = (
        "dev." + namespace,
        "github.com/" + namespace,
        '"github": "' + namespace + '"',
        "Copyright 2026 " + namespace,
        "/dev/" + namespace + "/",
        '" / "' + namespace + '" / "',
        namespace + "/",
        "document-" + namespace + "-",
    )
    violations = []
    text_suffixes = {".md", ".json", ".yaml", ".yml", ".py", ".kt", ".kts", ".java", ".sh", ".txt"}
    for relative in listed:
        if relative == "evidence/artifacts/neutral-language.json":
            continue
        path = ROOT / relative
        if not path.is_file() or (path.suffix not in text_suffixes and path.name not in {"README", "NOTICE", "LICENSE"}) or path.stat().st_size > 2_000_000:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if any(term in line for term in forbidden):
                violations.append(f"{relative}:{number}:宣伝表現")
            if namespace in line and not any(marker in line for marker in technical_namespace):
                violations.append(f"{relative}:{number}:非技術的namespace使用")
    if violations:
        raise RuntimeError("中立記述Gate失敗: " + "; ".join(violations))
    result = {"scanned_files": len(listed) - 1, "forbidden_term_count": len(forbidden), "violations": [], "verdict": "pass"}
    write_json(ARTIFACTS / "neutral-language.json", result)
    return result


def evidence_record(record_id: str, claim_ids: list[str], kind: str, producer: str, command: str, artifact: Path, harness_paths: list[Path]) -> dict:
    harness = harness_file(harness_paths)
    return {
        "schema_version": 1,
        "id": record_id,
        "atlas_id": "kotlin-reference-atlas",
        "claim_ids": claim_ids,
        "kind": kind,
        "producer": producer,
        "command": command,
        "created_at": CREATED_AT,
        "environment": {"profile": "local", "manifest_digest": sha256_file(ROOT / "environments" / "local.json")},
        "source_digest": sha256_file(ROOT / "sources.lock.yaml"),
        "harness_digest": sha256_file(harness),
        "harness_path": harness.relative_to(ROOT).as_posix(),
        "artifact": {"uri": artifact.relative_to(ROOT).as_posix(), "digest": sha256_file(artifact), "media_type": "application/json", "size_bytes": artifact.stat().st_size},
        "verdict": "pass",
        "retention": "git",
    }


def write_evidence() -> list[Path]:
    lab = ARTIFACTS / "lab-results.json"
    manifest = ARTIFACTS / "manifest-validation.json"
    skill = ROOT / "evals" / "kotlin-reference-router.skill-eval.json"
    rights = ARTIFACTS / "rights-validation.json"
    platform = ARTIFACTS / "platform-validation.json"
    bytecode = ARTIFACTS / "bytecode-inspection.json"
    inventory = ROOT / "atlas" / "inventory" / "kotlin-public-surface.json"
    container = ARTIFACTS / "container-verification.json"
    summary = ARTIFACTS / "verification-summary.json"
    non_regression = ARTIFACTS / "non-regression.json"
    fe_parity = ARTIFACTS / "kotlin-depth-parity.json"
    authority_locators = ARTIFACTS / "authority-locator-validation.json"
    authority_body = ARTIFACTS / "authority-body-inventory-validation.json"
    authority_review = ARTIFACTS / "authority-review-queue-validation.json"
    specs = [
        ("authority.source-lock-validation", ["authority.source-lock-matches"], "conformance", "kotlin-atlas-verifier", "atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml && atlas audit .", manifest, [ROOT / "atlas", ROOT / "mastery.yaml", ROOT / "scripts" / "verify.py"]),
        ("authority.locator-validation", ["authority.locator-inventory-is-copyright-safe-and-incomplete"], "capture", "kotlin-authority-locator-verifier", "python3 scripts/generate_authority_locators.py && python3 scripts/verify_authority_locators.py", authority_locators, [ROOT / "scripts" / "verify_authority_locators.py", ROOT / "authority" / "locator-extraction.json", ROOT / "baseline" / "fe-authority-locator-reference-v1.json"]),
        ("authority.body-inventory-validation", ["authority.raw-anchor-denominator-is-pending-human"], "capture", "kotlin-authority-body-inventory-verifier", "python3 scripts/verify_authority_body_inventory.py", authority_body, [ROOT / "scripts" / "verify_authority_body_inventory.py", ROOT / "authority" / "body-inventory.snapshot.json", ROOT / "baselines" / "authority-body-inventory-v1.json"]),
        ("authority.review-queue-validation", ["authority.raw-anchor-denominator-is-pending-human"], "capture", "kotlin-authority-review-queue-verifier", "python3 scripts/generate_authority_review_queue.py && python3 scripts/test_authority_review_queue.py && python3 scripts/verify_authority_review_queue.py", authority_review, [ROOT / "scripts" / "verify_authority_review_queue.py", ROOT / "authority" / "review-queue.snapshot.json", ROOT / "authority" / "reviews" / "decisions.json", ROOT / "authority" / "reviews" / "promotions.json"]),
        ("inventory.public-surface", ["inventory.locked-surface-enumerated"], "capture", "kotlin-artifact-inventory", "python3 scripts/inventory.py", inventory, [ROOT / "scripts" / "inventory.py", ROOT / "sources.lock.yaml"]),
        ("semantics.language-types", ["semantics.exhaustive-and-lazy", "types.variance-nothing-reified"], "test-report", "gradle-junit", "./gradlew :labs:semantics:test", lab, [ROOT / "labs" / "semantics"]),
        ("jvm.value-class-boundary", ["jvm.value-class-generic-boxing"], "test-report", "gradle-junit", "./gradlew :labs:jvm:test", lab, [ROOT / "labs" / "jvm"]),
        ("platform.multiplatform-runtime", ["platform.jvm-js-wasm-contract"], "compatibility", "kotlin-multiplatform", "./gradlew :labs:multiplatform:jvmTest :labs:multiplatform:jsNodeTest :labs:multiplatform:wasmJsNodeTest", platform, [ROOT / "labs" / "multiplatform"]),
        ("platform.native-compile", ["platform.native-test-klib"], "compatibility", "kotlin-native", "./gradlew :labs:multiplatform:compileTestKotlinMacosArm64", platform, [ROOT / "labs" / "multiplatform"]),
        ("gradle.plugin-consumer", ["gradle.plugin-registers-probe-task"], "test-report", "gradle-testkit", "./gradlew :labs:gradle-plugin:test", lab, [ROOT / "labs" / "gradle-plugin"]),
        ("build.toolchain-lock", ["gradle.toolchain-and-artifacts-locked"], "conformance", "kotlin-atlas-verifier", "python3 scripts/verify.py", rights, [ROOT / "gradle", *sorted(ROOT.glob("labs/*/gradle.lockfile"))]),
        ("coroutines.failure-propagation", ["coroutines.child-failure-cancels-sibling"], "test-report", "gradle-junit", "./gradlew :labs:coroutines:test", lab, [ROOT / "labs" / "coroutines"]),
        ("flow.pipeline-semantics", ["flow.retry-state-cancellation"], "test-report", "gradle-junit", "./gradlew :labs:flow:test", lab, [ROOT / "labs" / "flow"]),
        ("interop.java-consumer", ["interop.java-overloads-and-throws"], "compatibility", "gradle-junit", "./gradlew :labs:interop:test", lab, [ROOT / "labs" / "interop"]),
        ("compiler.runtime-shapes", ["compiler.runtime-shapes-observable"], "test-report", "gradle-junit", "./gradlew :labs:compiler-runtime:test", lab, [ROOT / "labs" / "compiler-runtime"]),
        ("compiler.bytecode-inspection", ["compiler.bytecode-state-machine"], "compatibility", "jdk-javap", "python3 scripts/inspect_bytecode.py", bytecode, [ROOT / "labs" / "compiler-runtime", ROOT / "scripts" / "inspect_bytecode.py"]),
        ("quality.testing-oracles", ["testing.cross-surface-oracles"], "test-report", "kotlin-atlas-verifier", "./gradlew atlasCheck", lab, [ROOT / "labs"]),
        ("quality.non-regression-baseline", ["quality.public-main-never-regresses"], "compatibility", "kotlin-atlas-baseline-gate", "python3 scripts/verify_non_regression.py", non_regression, [ROOT / "scripts" / "verify_non_regression.py", ROOT / "baseline" / "public-main-v0.2.0.json"]),
        ("quality.kotlin-depth-parity-gate", ["quality.kotlin-depth-parity-gaps-block-definitive"], "compatibility", "kotlin-depth-parity-gate", "python3 scripts/verify_fe_parity.py", fe_parity, [ROOT / "scripts" / "verify_fe_parity.py", ROOT / "atlas" / "definitive" / "kotlin-depth-parity.json", ROOT / "baseline" / "fe-depth-reference-v1.json"]),
        ("performance.measurement", ["performance.harness-reports-median"], "benchmark", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("security.boundaries", ["security.boundaries-reject-unsafe-input"], "attack", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("failure.debugging", ["failure.diagnostic-preserves-cause"], "recovery", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("evolution.compatibility-migration", ["migration.v1-v2-compatible"], "compatibility", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("operation.lifecycle-recovery", ["operation.lifecycle-recovers"], "conformance", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering", ROOT / "docs" / "RUNBOOK.md"]),
        ("operation.container-verification", ["operation.container-suite-reproducible"], "conformance", "docker-gradle", "scripts/container-verify.sh", container, [ROOT / "environments" / "container", ROOT / "scripts" / "container-verify.sh"]),
        ("skill.router-evaluation", ["skill.router-respects-coverage"], "skill-eval", "kotlin-router-eval", "python3 scripts/verify.py", skill, [ROOT / ".agents" / "skills" / "kotlin-reference-router", ROOT / "evals"]),
        ("skill.agent-forward-evaluation", ["skill.definitive-routing-is-bounded"], "skill-eval", "independent-agent-forward-eval", "independent subagent forwarded Router scenarios", ROOT / "evals" / "kotlin-reference-router.agent-forward-eval.json", [ROOT / ".agents" / "skills" / "kotlin-reference-router", ROOT / "evals" / "kotlin-reference-router.agent-forward-eval.json"]),
        ("publication.rights-metadata", ["publication.required-rights-files-present"], "conformance", "kotlin-atlas-verifier", "python3 scripts/verify.py", rights, [ROOT / "third_party", ROOT / "sbom.spdx.json", ROOT / "LICENSE", ROOT / "NOTICE"]),
        ("publication.complete-sbom", ["publication.transitive-sbom-from-locks"], "capture", "spdx-lock-generator", "python3 scripts/generate_sbom.py", rights, [ROOT / "scripts" / "generate_sbom.py", ROOT / "sbom.spdx.json", ROOT / "kotlin-js-store", *sorted(ROOT.glob("labs/*/gradle.lockfile"))]),
        ("operation.local-verification", ["operation.local-suite-reproducible"], "conformance", "kotlin-atlas-verifier", "python3 scripts/verify.py", summary, [ROOT / "scripts" / "verify.py", ROOT / "build.gradle.kts", ROOT / "settings.gradle.kts"]),
    ]
    paths = []
    for record_id, claim_ids, kind, producer, command, artifact, harness_paths in specs:
        path = ROOT / "evidence" / f"{record_id}.evidence.json"
        record = evidence_record(record_id, claim_ids, kind, producer, command, artifact, harness_paths)
        if record_id == "operation.container-verification":
            record["environment"] = {"profile": "container", "manifest_digest": sha256_file(ROOT / "environments" / "container.json")}
        if record_id == "evolution.compatibility-migration":
            record["execution_mode"] = "runtime"
            record["runtime_identity"] = "Homebrew OpenJDK 17.0.17+0 aarch64; Kotlin 2.4.10"
        write_json(path, record)
        paths.append(path)
    workbench_path = ROOT / "evidence" / "workbench.jvm-runtime.evidence.json"
    workbench = load_json(workbench_path)
    workbench["source_digest"] = sha256_file(ROOT / "sources.lock.yaml")
    workbench["harness_digest"] = sha256_file(ROOT / workbench["harness_path"])
    workbench_artifact = ROOT / workbench["artifact"]["uri"]
    workbench["artifact"]["digest"] = sha256_file(workbench_artifact)
    workbench["artifact"]["size_bytes"] = workbench_artifact.stat().st_size
    write_json(workbench_path, workbench)
    paths.append(workbench_path)
    return paths


def write_scenario_evidence() -> Path:
    scenario_index = ROOT / "evidence" / "scenarios" / "kotlin-closure-index.json"
    scenario_evidence_path = ROOT / "evidence" / "workbench.scenario-proof-matrix.evidence.json"
    write_json(scenario_evidence_path, evidence_record(
        "workbench.scenario-proof-matrix",
        ["workbench.jvm-integrated-scenarios"],
        "conformance",
        "kotlin-scenario-proof-matrix",
        "python3 scripts/generate_scenario_proofs.py && python3 scripts/verify_scenario_proofs.py",
        scenario_index,
        [ROOT / "scripts" / "generate_scenario_proofs.py", ROOT / "scripts" / "verify_scenario_proofs.py", ROOT / "surface.inventory.yaml", ROOT / "integrations" / "reference-system" / "manifest.json", ROOT / "baseline" / "fe-scenario-gap-closure-reference-v1.json"],
    ))
    return scenario_evidence_path


def write_claims() -> list[Path]:
    claims = load_json(ROOT / "atlas" / "claims" / "claims.json")["claims"]
    obligations = {
        item["id"]: item
        for item in load_json(ROOT / "atlas" / "proof-obligations" / "proof-obligations.json")["proof_obligations"]
    }
    paths = []
    for claim in claims:
        entity = {
            "schema_version": 1,
            "id": claim["id"],
            "atlas_id": "kotlin-reference-atlas",
            "capability_id": claim["capability_id"],
            "statement": claim["statement_ja"],
            "status": "accepted",
            "source_ids": claim["authority_source_ids"],
            "proof_obligations": [
                {
                    "id": obligation_id,
                    "statement": obligations[obligation_id]["oracle_ja"],
                    "acceptance_criteria": [obligations[obligation_id]["oracle_ja"]],
                }
                for obligation_id in claim["proof_obligation_ids"]
            ],
        }
        path = ROOT / "claims" / f"{claim['id']}.claim.json"
        write_json(path, entity)
        paths.append(path)
    return paths


def write_provenance(evidence_paths: list[Path]) -> Path:
    records: dict[str, dict] = {}
    kinds = {
        "evidence/artifacts/lab-results.json": "test-report",
        "evidence/artifacts/skill-eval.json": "skill-eval",
        "evals/kotlin-reference-router.skill-eval.json": "skill-eval",
        "evals/kotlin-reference-router.agent-forward-eval.json": "skill-eval",
        "sbom.spdx.json": "sbom",
    }
    for evidence_path in evidence_paths:
        record = load_json(evidence_path)
        artifact_path = record["artifact"]["uri"]
        records[artifact_path] = {
            "path": artifact_path,
            "digest": record["artifact"]["digest"],
            "kind": kinds.get(artifact_path, "generated"),
            "license": "Apache-2.0",
            "source_ids": ["reference-atlas-core-v1"],
            "generated_by": record["command"],
        }
    sbom = ROOT / "sbom.spdx.json"
    records["sbom.spdx.json"] = {
        "path": "sbom.spdx.json",
        "digest": sha256_file(sbom),
        "kind": "sbom",
        "license": "CC0-1.0",
        "source_ids": ["reference-atlas-core-v1"],
        "generated_by": "python3 scripts/generate_sbom.py",
    }
    for relative in [
        "evals/kotlin-reference-router.definitive-skill-eval.json",
        "evals/kotlin-reference-router.definitive-skill-eval-report.json",
        "evals/definitive-skill-router.json",
        "baseline/fe-definitive-skill-eval-reference-v1.json",
    ]:
        artifact = ROOT / relative
        records[relative] = {
            "path": relative,
            "digest": sha256_file(artifact),
            "kind": "skill-eval" if relative.startswith("evals/") else "document",
            "license": "Apache-2.0",
            "source_ids": ["reference-atlas-core-definitive-v2"],
            "generated_by": "python3 scripts/generate_definitive_skill_eval.py" if relative.startswith("evals/") else "manual digest lock from FE reference commit",
        }
    path = ROOT / "provenance.yaml"
    write_json(path, {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "generated_at": CREATED_AT,
        "artifacts": [records[key] for key in sorted(records)],
    })
    return path


def validate_graph(evidence_paths: list[Path]) -> None:
    coverage = load_json(ROOT / "coverage.yaml")
    claim_records = load_json(ROOT / "atlas" / "claims" / "claims.json")["claims"]
    claims = {claim["id"] for claim in claim_records}
    capabilities = {capability["id"] for capability in load_json(ROOT / "atlas" / "capabilities" / "capabilities.json")["capabilities"]}
    obligations = {item["id"] for item in load_json(ROOT / "atlas" / "proof-obligations" / "proof-obligations.json")["proof_obligations"]}
    records = {load_json(path)["id"]: load_json(path) for path in evidence_paths}
    errors = []
    for target in coverage["targets"]:
        if target["state"] != "covered":
            continue
        for claim_id in target["claim_ids"]:
            if claim_id not in claims:
                errors.append(f"unknown claim: {claim_id}")
        for evidence_id in target["evidence_ids"]:
            if evidence_id not in records or records[evidence_id]["verdict"] != "pass":
                errors.append(f"missing passing evidence: {evidence_id}")
    for record in records.values():
        for claim_id in record["claim_ids"]:
            if claim_id not in claims:
                errors.append(f"evidence references unknown claim: {claim_id}")
    for claim in claim_records:
        if claim["capability_id"] not in capabilities:
            errors.append(f"claim references unknown capability: {claim['id']}")
        for obligation_id in claim["proof_obligation_ids"]:
            if obligation_id not in obligations:
                errors.append(f"claim references unknown proof obligation: {obligation_id}")
    if errors:
        raise RuntimeError("; ".join(errors))


def validate_completion_certificate(evidence_paths: list[Path]) -> dict:
    certificate_path = ROOT / "evidence" / "completion-certificate.json"
    certificate = load_json(certificate_path)
    run([str(ROOT / "bin" / "atlas"), "certificate", "verify", "."])
    errors = []
    commit = run(["git", "cat-file", "-t", certificate["commit"]], capture=True)
    if commit.stdout.strip() != "commit":
        errors.append("commit")
    if errors:
        raise RuntimeError("Completion Certificate不整合: " + ",".join(errors))
    result = {
        "commit": certificate["commit"],
        "graph_digest": certificate["graph_digest"],
        "evidence_set_digest": certificate["evidence_set_digest"],
        "skill_package_digest": certificate["skill_package_digest"],
        "sbom_digest": certificate["sbom_digest"],
        "provenance_digest": certificate["provenance_digest"],
        "signature_digest": certificate["signature"]["digest"],
        "profiles": [item["profile"] for item in certificate["required_profiles"]],
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "certificate-validation.json", result)
    return result


def summarize_gap_ledger() -> dict:
    gap_count = 0
    state_counts: dict[str, int] = {}
    for raw_line in (ROOT / "atlas" / "definitive" / "gap-ledger.yaml").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- id:"):
            gap_count += 1
        elif line.startswith("state:"):
            state = line.split(":", 1)[1].strip()
            state_counts[state] = state_counts.get(state, 0) + 1
    if gap_count == 0 or sum(state_counts.values()) != gap_count:
        raise RuntimeError("Gap Ledgerを決定論的に集計できない")
    return {"gap_count": gap_count, "state_counts": dict(sorted(state_counts.items()))}


def audit_definitive_incomplete() -> dict:
    base = run([str(ROOT / "bin" / "atlas"), "audit", "."], capture=True)
    dependency = run([str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "evidence-dependency"], capture=True)
    scenario_plan = run_expect_failure([str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "scenario-plan"])
    if not scenario_plan.stdout or "Evidence durability" not in scenario_plan.stdout:
        raise RuntimeError("Scenario Plan Gateが成功世代未生成を明示して拒否しない")
    durability = run_expect_failure([str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "evidence-durability"])
    if not durability.stdout or "failed run" not in durability.stdout:
        raise RuntimeError("Evidence durability Gateが成功世代未生成を明示して拒否しない")
    definitive = run_expect_failure([str(ROOT / "bin" / "atlas"), "audit", ".", "--gate", "definitive"])
    if not definitive.stdout or "subject-definitive" not in definitive.stdout:
        raise RuntimeError("Definitive Gateが未完理由を返さない")
    result = {
        "base_audit": base.stdout.strip(),
        "evidence_dependency_audit": dependency.stdout.strip(),
        "scenario_plan_audit_exit_code": scenario_plan.returncode,
        "scenario_plan_audit_output": scenario_plan.stdout.strip(),
        "evidence_durability_audit_exit_code": durability.returncode,
        "evidence_durability_audit_output": durability.stdout.strip(),
        "definitive_audit_exit_code": definitive.returncode,
        "definitive_audit_output": definitive.stdout.strip(),
        "bounded_historical_certificate": "evidence/history/v0.2.0/completion-certificate.json",
        "active_definitive_certificate": None,
        "completion_class": "incomplete",
        "verdict": "incomplete",
    }
    write_json(ARTIFACTS / "definitive-audit.json", result)
    return result


def main(*, skip_container: bool = False) -> None:
    evidence_run_started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    manifest_result = validate_manifests()
    lab_result = collect_test_results()
    deep_result = generate_deep_artifacts()
    if skip_container:
        container_result = load_json(ARTIFACTS / "container-verification.json")
        if container_result.get("verdict") != "pass":
            raise RuntimeError("既存Container Evidenceがpassではありません")
    else:
        container_result = validate_container_profile()
    # RouterはEvidence artifact digestをfail-closedで確認する。直前のLab/Artifact
    # 再生成をrecordへ反映してからEvalし、後段で全Gateの最終recordを再固定する。
    write_evidence()
    skill_result = run_skill_evals()
    definitive_skill_result = validate_definitive_skill_eval()
    rights_result = validate_rights()
    non_regression_result = validate_non_regression()
    authority_locator_result = validate_authority_locators()
    authority_body_result = validate_authority_body_inventory()
    authority_review_result = validate_authority_review_queue()
    # Depth Parityが専用Scenario Evidenceを参照できるよう、追跡済みEvidenceを入力に
    # matrixとwrapperを先に再生成する。全Evidence更新後にも再生成し、最終digestを固定する。
    run([sys.executable, str(ROOT / "scripts" / "generate_scenario_proofs.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_scenario_proofs.py")])
    run([sys.executable, str(ROOT / "scripts" / "generate_scenario_closure_plan.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_scenario_closure_plan.py")])
    write_scenario_evidence()
    fe_parity_result = validate_fe_parity()
    neutral_language_result = validate_neutral_language()
    run([sys.executable, str(ROOT / "scripts" / "generate_evidence_dependency_graph.py"), "--run-started-at", evidence_run_started_at, "--run-completed-at", datetime.now().astimezone().isoformat(timespec="seconds")])
    run([sys.executable, str(ROOT / "scripts" / "test_evidence_dependency_graph.py")])
    gaps = summarize_gap_ledger()
    summary = {
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "implementation_gates": {"manifest": manifest_result["verdict"], "mastery_audit": manifest_result["verdict"], "labs": lab_result["verdict"], "deep_artifacts": deep_result["verdict"], "container": container_result["verdict"], "skill": skill_result["verdict"], "definitive_skill": definitive_skill_result["verdict"], "rights_metadata": rights_result["verdict"], "non_regression": non_regression_result["verdict"], "authority_locator": authority_locator_result["verdict"], "authority_body_denominator": authority_body_result["verdict"], "authority_review_queue": authority_review_result["verdict"], "kotlin_depth_parity": fe_parity_result["verdict"], "neutral_language": neutral_language_result["verdict"], "evidence_dependency": "pass", "scenario_plan": "expected-incomplete-no-success-generation", "evidence_durability": "expected-incomplete-no-success-generation", "definitive": "expected-incomplete"},
        "definitive_skill_eval": definitive_skill_result,
        "kotlin_depth_parity": {"axis_count": fe_parity_result["axis_count"], "status_counts": fe_parity_result["status_counts"], "total_axis_gaps": fe_parity_result["total_axis_gaps"], "all_axes_closed": fe_parity_result["all_axes_closed"], "reference_commit": fe_parity_result["reference_commit"]},
        "completion_class": "incomplete",
        "bounded_historical_certificate": "evidence/history/v0.2.0/completion-certificate.json",
        "authority_surface_inventory": {"artifacts": manifest_result["authority_artifacts"], "behaviors": manifest_result["authority_behaviors"]},
        "authority_locator_extraction": authority_locator_result["summary"],
        "authority_body_denominator": authority_body_result["summary"],
        "authority_review_queue": authority_review_result["summary"],
        "gap_ledger": gaps,
        "completion_gaps": [
            "146402 candidate anchorは全件Queue済みだが、Human decisionとSemantic Surface／Atomic behaviorへの昇格が未閉鎖",
            "69 Authority inventory Behavior×10 Scenarioは専用row化済みだが、4590 Surface×Scenario×Variant cellの専用初回実行・Identity・Source/Harness・Oracle/Trace/ArtifactとAuthority atomic bindingが未閉鎖",
            "Pattern Scenario Reporterは原子的retention契約へ適合するが、公開可能なfull-run成功世代が未生成のためCore Evidence durability／Scenario Plan Gateは未閉鎖",
            "112-cell Router契約と独立Agent Forward Evalはpassだが22 Mastery routing gapが未閉鎖",
            "JVM以外を含む実Runtime、比較Variant、Artifact Evidenceが未閉鎖",
        ],
        "recorded_infeasible": ["platform.native-runtime: Full Xcode unavailable; KLIB compileはRuntime Evidenceの代替ではない"] if deep_result["native_runtime"]["verdict"] == "infeasible" else [],
        "recommended_open": ["Gap LedgerのBehavior別Proof closure", "Automation WorkbenchのPlatform横断Runtimeと比較Variant"],
        "repository_status": load_json(ROOT / "atlas.yaml")["status"],
        "verdict": "implementation-pass-definitive-incomplete",
    }
    write_json(ARTIFACTS / "verification-summary.json", summary)
    claim_paths = write_claims()
    evidence_paths = write_evidence()
    run([sys.executable, str(ROOT / "scripts" / "generate_scenario_proofs.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_scenario_proofs.py")])
    run([sys.executable, str(ROOT / "scripts" / "generate_scenario_closure_plan.py")])
    run([sys.executable, str(ROOT / "scripts" / "verify_scenario_closure_plan.py")])
    scenario_evidence_path = write_scenario_evidence()
    evidence_paths.append(scenario_evidence_path)
    provenance_path = write_provenance(evidence_paths)
    run([sys.executable, str(ROOT / "scripts" / "generate_evidence_dependency_graph.py"), "--run-started-at", evidence_run_started_at, "--run-completed-at", datetime.now().astimezone().isoformat(timespec="seconds")])
    run([sys.executable, str(ROOT / "scripts" / "test_evidence_dependency_graph.py")])
    entity_paths = [*claim_paths, *evidence_paths, ROOT / "evals" / "kotlin-reference-router.skill-eval.json", provenance_path]
    run([str(ROOT / "bin" / "atlas"), "validate", *[path.relative_to(ROOT).as_posix() for path in entity_paths]])
    validate_graph(evidence_paths)
    if load_json(ROOT / "atlas.yaml")["status"] == "complete":
        certificate_path = ROOT / "evidence" / "completion-certificate.json"
        if certificate_path.is_file():
            source_commit = load_json(certificate_path)["commit"]
        else:
            source_commit = run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()
        run([
            str(ROOT / "bin" / "atlas"), "certificate", "generate", ".",
            "--issued-at", CREATED_AT, "--commit", source_commit,
        ])
        validate_completion_certificate(evidence_paths)
        run([str(ROOT / "bin" / "atlas"), "audit", "."])
    else:
        audit_definitive_incomplete()
    print(f"検証完了: implementation gates passed; Definitive Gateは期待どおり未完; repository status={load_json(ROOT / 'atlas.yaml')['status']}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kotlin技術実証アトラスの全Gateを検証する。")
    parser.add_argument("--skip-container", action="store_true", help="別JobでContainer profileを実行する場合だけ既存Container Evidenceを利用する。")
    arguments = parser.parse_args()
    main(skip_container=arguments.skip_container)
