#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "baseline" / "public-main-v0.2.0.json"
OUTPUT = ROOT / "evidence" / "artifacts" / "non-regression.json"
ASSERTION = re.compile(r"(?:assert[A-Z][A-Za-z0-9_]*|assertThrows|fail)\s*\(")
DISABLED = re.compile(r"@(?:Disabled|Ignore)\b|\benabled\s*=\s*false\b|\bdisabled\s*=\s*true\b", re.IGNORECASE)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest_json(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def ids(document: dict, collection: str) -> set[str]:
    return {item["id"] for item in document[collection]}


def git_bytes(commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"baseline Git objectを読めない: {path}")
    return result.stdout


def git_json(commit: str, path: str) -> dict:
    return json.loads(git_bytes(commit, path).decode())


def validate_baseline_capture(baseline: dict, errors: list[str]) -> None:
    commit = baseline["source_commit"]
    published_coverage = git_json(commit, "coverage.yaml")
    if baseline["targets"] != [
        {key: item[key] for key in ("id", "requirement", "state")}
        for item in published_coverage["targets"]
    ]:
        errors.append("Baseline Target captureが固定mainと一致しない")
    if baseline["target_sets"] != [item["id"] for item in published_coverage["target_sets"]]:
        errors.append("Baseline Target Set captureが固定mainと一致しない")
    published_sets = {
        "capability_ids": [item["id"] for item in git_json(commit, "atlas/capabilities/capabilities.json")["capabilities"]],
        "claim_ids": [item["id"] for item in git_json(commit, "atlas/claims/claims.json")["claims"]],
        "proof_obligation_ids": [item["id"] for item in git_json(commit, "atlas/proof-obligations/proof-obligations.json")["proof_obligations"]],
    }
    for key, expected in published_sets.items():
        if baseline[key] != expected:
            errors.append(f"Baseline {key} captureが固定mainと一致しない")
    published_sources = [
        {key: item[key] for key in ("id", "version", "digest")}
        for item in git_json(commit, "sources.lock.yaml")["sources"]
    ]
    if baseline["sources"] != published_sources:
        errors.append("Baseline Source captureが固定mainと一致しない")
    published_cases = git_json(commit, "evals/router-cases.json")["cases"]
    published_case_digests = {item["id"]: digest_json(item) for item in published_cases}
    if baseline["skill_eval_case_digests"] != published_case_digests:
        errors.append("Baseline Skill Eval captureが固定mainと一致しない")
    for expected in baseline["evidence"]:
        document = git_json(commit, f"evidence/{expected['id']}.evidence.json")
        actual = {key: document[key] for key in ("id", "kind", "command")}
        if actual != expected:
            errors.append(f"Baseline Evidence captureが固定mainと一致しない: {expected['id']}")
    for expected in baseline["test_files"]:
        source = git_bytes(commit, expected["path"])
        text = source.decode()
        actual = {
            "path": expected["path"],
            "tests": text.count("@Test"),
            "assertions": len(ASSERTION.findall(text)),
            "sha256": hashlib.sha256(source).hexdigest(),
        }
        if actual != expected:
            errors.append(f"Baseline Test captureが固定mainと一致しない: {expected['path']}")
    published_settings = git_bytes(commit, "settings.gradle.kts").decode()
    published_build = git_bytes(commit, "build.gradle.kts").decode()
    published_ci = git_bytes(commit, ".github/workflows/ci.yml").decode()
    if any(f'"{item}"' not in published_settings for item in baseline["lab_modules"]):
        errors.append("Baseline Lab module captureが固定mainと一致しない")
    if any(f'"{item}"' not in published_build for item in baseline["atlas_check_tasks"]):
        errors.append("Baseline atlasCheck captureが固定mainと一致しない")
    if any(item not in published_ci for item in baseline["ci_required_tokens"]):
        errors.append("Baseline CI captureが固定mainと一致しない")


def main() -> None:
    baseline = load(BASELINE_PATH)
    errors: list[str] = []
    replacements = {item["old_id"]: item for item in baseline["replacements"]}
    for item in replacements.values():
        required = {"old_id", "new_id", "reason", "migration_evidence", "proof_ids"}
        if not required.issubset(item) or not item["proof_ids"] or not (ROOT / item["migration_evidence"]).is_file():
            errors.append(f"置換契約が不完全: {item.get('old_id', '<unknown>')}")

    commit = subprocess.run(
        ["git", "cat-file", "-e", baseline["source_commit"] + "^{commit}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if commit.returncode != 0:
        errors.append("public main baseline commitをGit objectとして検証できない")
    else:
        validate_baseline_capture(baseline, errors)

    coverage = load(ROOT / "coverage.yaml")
    current_targets = {item["id"]: item for item in coverage["targets"]}
    baseline_targets = {item["id"]: item for item in baseline["targets"]}
    for target_id, expected in baseline_targets.items():
        actual = current_targets.get(target_id)
        if actual is None:
            errors.append(f"Target削除: {target_id}")
            continue
        if expected["requirement"] == "required" and actual["requirement"] != "required":
            errors.append(f"required格下げ: {target_id}")
        allowed = {
            "covered": {"covered"},
            "infeasible": {"infeasible", "covered"},
            "planned": {"planned", "partial", "covered"},
        }[expected["state"]]
        if actual["state"] not in allowed:
            errors.append(f"Target状態後退: {target_id} {expected['state']} -> {actual['state']}")
    for target_id, actual in current_targets.items():
        if actual["state"] in {"excluded", "infeasible"} and target_id not in baseline_targets:
            errors.append(f"新規Scope外退避: {target_id} state={actual['state']}")
    current_target_sets = {item["id"] for item in coverage["target_sets"]}
    for target_set in baseline["target_sets"]:
        if target_set not in current_target_sets:
            errors.append(f"Target Set削除: {target_set}")

    canonical_sets = {
        "capabilities": ids(load(ROOT / "atlas" / "capabilities" / "capabilities.json"), "capabilities"),
        "claims": ids(load(ROOT / "atlas" / "claims" / "claims.json"), "claims"),
        "proof_obligations": ids(load(ROOT / "atlas" / "proof-obligations" / "proof-obligations.json"), "proof_obligations"),
    }
    for label, key in (("Capability", "capability_ids"), ("Claim", "claim_ids"), ("Proof", "proof_obligation_ids")):
        collection = canonical_sets[{"Capability": "capabilities", "Claim": "claims", "Proof": "proof_obligations"}[label]]
        for expected_id in baseline[key]:
            if expected_id not in collection and expected_id not in replacements:
                errors.append(f"{label}削除: {expected_id}")

    current_sources = {item["id"]: item for item in load(ROOT / "sources.lock.yaml")["sources"]}
    for expected in baseline["sources"]:
        actual = current_sources.get(expected["id"])
        if actual is None:
            errors.append(f"Source削除: {expected['id']}")
        elif (actual["version"], actual["digest"]) != (expected["version"], expected["digest"]):
            if expected["id"] not in replacements:
                errors.append(f"Source固定値の置換: {expected['id']}")

    current_evidence = {
        document["id"]: document
        for path in (ROOT / "evidence").glob("*.evidence.json")
        for document in [load(path)]
    }
    for expected in baseline["evidence"]:
        actual = current_evidence.get(expected["id"])
        if actual is None:
            errors.append(f"Evidence削除: {expected['id']}")
            continue
        if actual.get("verdict") != "pass":
            errors.append(f"baseline Evidence失敗または削除: {expected['id']}")
        if (actual.get("kind"), actual.get("command")) != (expected["kind"], expected["command"]):
            if expected["id"] not in replacements:
                errors.append(f"Evidence実行Proof置換: {expected['id']}")
        if actual.get("execution_mode") in {"mock", "static", "fixture", "compile-only"}:
            errors.append(f"Evidenceを非Runtimeへ置換: {expected['id']}")

    settings = (ROOT / "settings.gradle.kts").read_text(encoding="utf-8")
    build = (ROOT / "build.gradle.kts").read_text(encoding="utf-8")
    for module in baseline["lab_modules"]:
        if f'"{module}"' not in settings:
            errors.append(f"Lab module削除: {module}")
    for task in baseline["atlas_check_tasks"]:
        if f'"{task}"' not in build:
            errors.append(f"atlasCheck task削除: {task}")

    total_tests = 0
    total_assertions = 0
    for expected in baseline["test_files"]:
        path = ROOT / expected["path"]
        if not path.is_file():
            errors.append(f"Test file削除: {expected['path']}")
            continue
        source = path.read_text(encoding="utf-8")
        tests = source.count("@Test")
        assertions = len(ASSERTION.findall(source))
        total_tests += tests
        total_assertions += assertions
        if tests < expected["tests"] or assertions < expected["assertions"]:
            errors.append(f"Test/Assertion縮小: {expected['path']} tests={tests} assertions={assertions}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected["sha256"] and expected["path"] not in replacements:
            errors.append(f"baseline Test変更にMigration mappingがない: {expected['path']}")
        if DISABLED.search(source):
            errors.append(f"Test disabled化: {expected['path']}")
    for path in sorted((ROOT / "labs").rglob("*Test.kt")) + sorted((ROOT / "reference-systems").rglob("*Test.kt")):
        if "build" not in path.parts and DISABLED.search(path.read_text(encoding="utf-8")):
            errors.append(f"Test disabled化: {path.relative_to(ROOT)}")

    lab_results = load(ROOT / "evidence" / "artifacts" / "lab-results.json")
    if lab_results["test_case_count"] < baseline["minimum_counts"]["test_cases"]:
        errors.append("実行Test case数がpublic mainを下回る")
    if any(case["status"] != "pass" for suite in lab_results["suites"] for case in suite["cases"]):
        errors.append("実行Testにfailまたはskipがある")

    eval_cases = {item["id"]: item for item in load(ROOT / "evals" / "router-cases.json")["cases"]}
    for case_id, expected_digest in baseline["skill_eval_case_digests"].items():
        actual = eval_cases.get(case_id)
        if actual is None:
            errors.append(f"Skill Eval削除: {case_id}")
        elif digest_json(actual) != expected_digest and case_id not in replacements:
            errors.append(f"Skill Eval期待値変更: {case_id}")

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for token in baseline["ci_required_tokens"]:
        if token not in workflow:
            errors.append(f"CI Matrix縮小: {token}")

    counts = {
        "targets": len(current_targets),
        "target_sets": len(current_target_sets),
        "capabilities": len(canonical_sets["capabilities"]),
        "claims": len(canonical_sets["claims"]),
        "proof_obligations": len(canonical_sets["proof_obligations"]),
        "evidence": len(current_evidence),
        "sources": len(current_sources),
        "skill_eval_cases": len(eval_cases),
        "baseline_test_annotations": total_tests,
        "baseline_assertions": total_assertions,
        "executed_test_cases": lab_results["test_case_count"],
    }
    for key in ("targets", "target_sets", "capabilities", "claims", "proof_obligations", "evidence", "sources", "skill_eval_cases"):
        if counts[key] < baseline["minimum_counts"][key]:
            errors.append(f"baseline count縮小: {key}={counts[key]}")

    result = {
        "schema_version": 1,
        "baseline_id": baseline["id"],
        "baseline_commit": baseline["source_commit"],
        "counts": counts,
        "baseline_minimum_counts": baseline["minimum_counts"],
        "replacements": baseline["replacements"],
        "violations": errors,
        "verdict": "pass" if not errors else "fail",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("非後退Gate失敗: " + "; ".join(errors))
    print(f"非後退Gate成功: baseline={baseline['source_commit']} counts={counts}")


if __name__ == "__main__":
    main()
