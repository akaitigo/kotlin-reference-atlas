#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

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
    run([str(ROOT / "gradlew"), "clean", "test", "--configuration-cache", "--no-daemon"])
    suites = []
    for report in sorted((ROOT / "labs").glob("*/build/test-results/test/TEST-*.xml")):
        xml_root = ET.parse(report).getroot()
        cases = []
        for case in xml_root.findall("testcase"):
            status = "pass"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "fail"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append({"class": case.attrib.get("classname", ""), "name": case.attrib.get("name", ""), "status": status})
        suites.append({"module": report.parts[-5], "suite": xml_root.attrib.get("name", ""), "cases": sorted(cases, key=lambda item: (item["class"], item["name"]))})
    if not suites or any(case["status"] != "pass" for suite in suites for case in suite["cases"]):
        raise RuntimeError("全LabのJUnit resultをpassとして収集できない")
    result = {"command": "./gradlew clean test --configuration-cache --no-daemon", "suites": suites, "verdict": "pass"}
    write_json(ARTIFACTS / "lab-results.json", result)
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
    if spdx.get("spdxVersion") != "SPDX-2.3" or not {"kotlin-reference-atlas", "reference-atlas-core", "kotlin", "gradle", "kotlinx-coroutines", "junit"}.issubset(spdx_names):
        errors.append("SPDX SBOMの必須Packageが不足")
    if sha256_file(ROOT / "gradle" / "wrapper" / "gradle-wrapper.jar") != "sha256:497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7":
        errors.append("Gradle Wrapper JAR checksumが9.5.0公式値と一致しない")
    wrapper_properties = (ROOT / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(encoding="utf-8")
    if "distributionSha256Sum=553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746" not in wrapper_properties:
        errors.append("Gradle distribution checksumが固定値と一致しない")
    if errors:
        raise RuntimeError("; ".join(errors))
    result = {"required_files": required, "direct_component_count": len(manifest["components"]), "sbom_formats": ["CycloneDX-1.6", "SPDX-2.3"], "sbom_scope": "direct-dependencies-only", "verdict": "pass"}
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
    summary = ARTIFACTS / "verification-summary.json"
    specs = [
        ("authority.source-lock-validation", ["authority.source-lock-matches"], "conformance", "kotlin-atlas-verifier", "atlas validate atlas.yaml mastery.yaml coverage.yaml sources.lock.yaml skill.package.yaml && atlas audit .", manifest, [ROOT / "atlas", ROOT / "mastery.yaml", ROOT / "scripts" / "verify.py"]),
        ("jvm.value-class-boundary", ["jvm.value-class-generic-boxing"], "test-report", "gradle-junit", "./gradlew :labs:jvm:test", lab, [ROOT / "labs" / "jvm"]),
        ("gradle.plugin-consumer", ["gradle.plugin-registers-probe-task"], "test-report", "gradle-testkit", "./gradlew :labs:gradle-plugin:test", lab, [ROOT / "labs" / "gradle-plugin"]),
        ("coroutines.failure-propagation", ["coroutines.child-failure-cancels-sibling"], "test-report", "gradle-junit", "./gradlew :labs:coroutines:test", lab, [ROOT / "labs" / "coroutines"]),
        ("interop.java-consumer", ["interop.java-overloads-and-throws"], "compatibility", "gradle-junit", "./gradlew :labs:interop:test", lab, [ROOT / "labs" / "interop"]),
        ("skill.router-evaluation", ["skill.router-respects-coverage"], "skill-eval", "kotlin-router-eval", "python3 scripts/verify.py", skill, [ROOT / ".agents" / "skills" / "kotlin-reference-router", ROOT / "evals"]),
        ("publication.rights-metadata", ["publication.required-rights-files-present"], "conformance", "kotlin-atlas-verifier", "python3 scripts/verify.py", rights, [ROOT / "third_party", ROOT / "sbom.spdx.json", ROOT / "LICENSE", ROOT / "NOTICE"]),
        ("operation.local-verification", ["operation.local-suite-reproducible"], "conformance", "kotlin-atlas-verifier", "python3 scripts/verify.py", summary, [ROOT / "scripts" / "verify.py", ROOT / "build.gradle.kts", ROOT / "settings.gradle.kts"]),
    ]
    paths = []
    for record_id, claim_ids, kind, producer, command, artifact, harness_paths in specs:
        path = ROOT / "evidence" / f"{record_id}.evidence.json"
        write_json(path, evidence_record(record_id, claim_ids, kind, producer, command, artifact, harness_paths))
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


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    manifest_result = validate_manifests()
    lab_result = collect_test_results()
    skill_result = run_skill_evals()
    rights_result = validate_rights()
    summary = {
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "implementation_gates": {"manifest": manifest_result["verdict"], "mastery_audit": manifest_result["verdict"], "labs": lab_result["verdict"], "skill": skill_result["verdict"], "rights_metadata": rights_result["verdict"]},
        "completion_gaps": ["operation.container-evidence", "publication.complete-sbom", "inventory.kotlin-public-surface", "reference-system.automation-workbench", "evidence/completion-certificate.json", "reference-atlas-core fixed release tag", "github-hosted CI execution"],
        "repository_status": "incomplete",
        "verdict": "pass",
    }
    write_json(ARTIFACTS / "verification-summary.json", summary)
    evidence_paths = write_evidence()
    run([str(ROOT / "bin" / "atlas"), "validate", *[path.relative_to(ROOT).as_posix() for path in evidence_paths]])
    validate_graph(evidence_paths)
    print("検証完了: Local implementation gates passed; completion status remains incomplete.")


if __name__ == "__main__":
    main()
