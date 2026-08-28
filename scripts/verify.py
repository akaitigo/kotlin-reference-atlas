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
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = "2026-08-28T00:00:00+09:00"
MANIFESTS = ["atlas.yaml", "mastery.yaml", "coverage.yaml", "sources.lock.yaml", "skill.package.yaml"]
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


def validate_manifests() -> dict:
    run([str(ROOT / "bin" / "atlas"), "validate", *MANIFESTS])
    audit = run([str(ROOT / "bin" / "atlas"), "audit", "."], capture=True)
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
    if atlas["status"] != "incomplete":
        errors.append("Completion Gate未通過中はstatus: incompleteでなければならない")
    if migration["unmapped_source_ids"]:
        errors.append("Core v1 migrationに未対応source IDがある")
    if migration["target"]["core_commit"] != core_version["commit"]:
        errors.append("MigrationとCore Versionのcommitが一致しない")
    if errors:
        raise RuntimeError("; ".join(errors))
    result = {
        "atlas_id": atlas["id"],
        "epoch": coverage["epoch"],
        "authority_lock_digest": expected_digest,
        "mastery_outcomes": len(mastery["outcomes"]),
        "mastery_surfaces": len(mastery["surfaces"]),
        "audit_output": audit.stdout.strip(),
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "manifest-validation.json", result)
    return result


def collect_test_results() -> dict:
    run([str(ROOT / "gradlew"), "clean", "atlasCheck", "--configuration-cache", "--no-daemon"])
    suites = []
    for report in sorted((ROOT / "labs").rglob("TEST-*.xml")):
        xml_root = ET.parse(report).getroot()
        cases = []
        for case in xml_root.findall("testcase"):
            status = "pass"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "fail"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append({"class": case.attrib.get("classname", ""), "name": case.attrib.get("name", ""), "status": status})
        relative = report.relative_to(ROOT / "labs")
        suites.append({"module": relative.parts[0], "task": report.parent.name, "suite": xml_root.attrib.get("name", ""), "cases": sorted(cases, key=lambda item: (item["class"], item["name"]))})
    if not suites or any(case["status"] != "pass" for suite in suites for case in suite["cases"]):
        raise RuntimeError("全LabのJUnit resultをpassとして収集できない")
    result = {"command": "./gradlew clean atlasCheck --configuration-cache --no-daemon", "suites": suites, "test_case_count": sum(len(suite["cases"]) for suite in suites), "verdict": "pass"}
    write_json(ARTIFACTS / "lab-results.json", result)
    return result


def generate_deep_artifacts() -> dict:
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
    xcode = subprocess.run(
        ["/usr/bin/xcrun", "xcodebuild", "-version"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if xcode.returncode == 0:
        raise RuntimeError("Full Xcodeを検出したためplatform.native-runtimeのinfeasible判定を再評価してください")
    result = {
        "jvm_runtime": "pass",
        "js_node_runtime": "pass",
        "wasm_node_runtime": "pass",
        "wasm_digest": sha256_file(wasm),
        "native_macos_arm64_compile": "pass",
        "native_test_klib_digest": digest_tree([native_klib]),
        "native_runtime": {
            "verdict": "infeasible" if xcode.returncode != 0 else "not-run",
            "xcodebuild_exit_code": xcode.returncode,
            "xcodebuild_output": xcode.stdout.strip(),
            "reason": "Full XcodeのxcodebuildがHostに存在しないためlinkDebugTestMacosArm64を実行できない" if xcode.returncode != 0 else "Full Xcodeを検出したためNative runtime Targetを再評価する必要がある",
        },
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
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    manifest = load_json(ROOT / "third_party" / "manifest.yaml")
    sbom = load_json(ROOT / "third_party" / "sbom.cdx.json")
    spdx = load_json(ROOT / "sbom.spdx.json")
    direct_ids = {item["id"] for item in manifest["components"] if item["id"] != "reference-atlas-core"}
    sbom_names = {item["name"] for item in sbom["components"]}
    errors = []
    if missing:
        errors.append("missing=" + ",".join(missing))
    if not {"kotlin", "gradle", "kotlinx-coroutines", "junit"}.issubset(direct_ids):
        errors.append("third_party manifestの直接依存が不足")
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
                expected_npm.add(f"pkg:npm/{path.rsplit('node_modules/', 1)[1]}@{package['version']}")
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
    result = {"required_files": required, "direct_component_count": len(manifest["components"]), "sbom_formats": ["CycloneDX-1.6", "SPDX-2.3"], "sbom_scope": "gradle-and-npm-lock-transitive-closure", "spdx_package_count": len(spdx["packages"]), "lock_component_count": len(expected_gradle | expected_npm), "missing_lock_components": [], "verdict": "pass"}
    write_json(ARTIFACTS / "rights-validation.json", result)
    return result


def evidence_record(record_id: str, claim_ids: list[str], kind: str, producer: str, command: str, artifact: Path, harness_paths: list[Path]) -> dict:
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
        "harness_digest": digest_tree(harness_paths),
        "artifact": {"uri": artifact.relative_to(ROOT).as_posix(), "digest": sha256_file(artifact), "media_type": "application/json", "size_bytes": artifact.stat().st_size},
        "verdict": "pass",
        "retention": "git",
    }


def write_evidence() -> list[Path]:
    lab = ARTIFACTS / "lab-results.json"
    manifest = ARTIFACTS / "manifest-validation.json"
    skill = ARTIFACTS / "skill-eval.json"
    rights = ARTIFACTS / "rights-validation.json"
    platform = ARTIFACTS / "platform-validation.json"
    bytecode = ARTIFACTS / "bytecode-inspection.json"
    inventory = ROOT / "atlas" / "inventory" / "kotlin-public-surface.json"
    container = ARTIFACTS / "container-verification.json"
    summary = ARTIFACTS / "verification-summary.json"
    specs = [
        ("authority.source-lock-validation", ["authority.source-lock-matches"], "conformance", "kotlin-atlas-verifier", "atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml && atlas audit .", manifest, [ROOT / "atlas", ROOT / "mastery.yaml", ROOT / "scripts" / "verify.py"]),
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
        ("performance.measurement", ["performance.harness-reports-median"], "benchmark", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("security.boundaries", ["security.boundaries-reject-unsafe-input"], "attack", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("failure.debugging", ["failure.diagnostic-preserves-cause"], "recovery", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("evolution.compatibility-migration", ["migration.v1-v2-compatible"], "compatibility", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering"]),
        ("operation.lifecycle-recovery", ["operation.lifecycle-recovers"], "conformance", "gradle-junit", "./gradlew :labs:engineering:test", lab, [ROOT / "labs" / "engineering", ROOT / "docs" / "RUNBOOK.md"]),
        ("operation.container-verification", ["operation.container-suite-reproducible"], "conformance", "docker-gradle", "scripts/container-verify.sh", container, [ROOT / "environments" / "container", ROOT / "scripts" / "container-verify.sh"]),
        ("skill.router-evaluation", ["skill.router-respects-coverage"], "skill-eval", "kotlin-router-eval", "python3 scripts/verify.py", skill, [ROOT / ".agents" / "skills" / "kotlin-reference-router", ROOT / "evals"]),
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
        write_json(path, record)
        paths.append(path)
    return paths


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


def main(*, skip_container: bool = False) -> None:
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
    skill_result = run_skill_evals()
    rights_result = validate_rights()
    summary = {
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "implementation_gates": {"manifest": manifest_result["verdict"], "mastery_audit": manifest_result["verdict"], "labs": lab_result["verdict"], "deep_artifacts": deep_result["verdict"], "container": container_result["verdict"], "skill": skill_result["verdict"], "rights_metadata": rights_result["verdict"]},
        "completion_gaps": ["platform.native-runtime: Full Xcode unavailable", "reference-system.automation-workbench (recommended)", "evidence/completion-certificate.json", "local release tag", "github-hosted CI execution"],
        "repository_status": "incomplete",
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "verification-summary.json", summary)
    evidence_paths = write_evidence()
    run([str(ROOT / "bin" / "atlas"), "validate", *[path.relative_to(ROOT).as_posix() for path in evidence_paths]])
    validate_graph(evidence_paths)
    print("検証完了: Local implementation gates passed; completion status remains incomplete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kotlin技術実証アトラスの全Gateを検証する。")
    parser.add_argument("--skip-container", action="store_true", help="別JobでContainer profileを実行する場合だけ既存Container Evidenceを利用する。")
    arguments = parser.parse_args()
    main(skip_container=arguments.skip_container)
