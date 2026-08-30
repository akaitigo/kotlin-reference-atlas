#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""macOS local/Ubuntu container CI Profile分離のnegative fixture。"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from verify_evidence_dependency_profile import verify

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
VERIFY_SOURCE = ROOT / "scripts" / "verify.py"
REPORT = ROOT / "evidence" / "artifacts" / "ci-profile-contract.json"

REQUIRED_VALIDATE = [
    "runs-on: macos-14",
    "python3 scripts/verify_python_dependency_contract.py --require-runtime --no-write --runtime-proof",
    "python-dependency-runtime-${{ github.run_id }}-${{ github.run_attempt }}",
    "python3 scripts/verify.py --skip-container",
]
REQUIRED_CONTAINER = [
    "runs-on: ubuntu-latest",
    "scripts/container-verify.sh",
    "python3 scripts/verify_evidence_dependency_profile.py --profile container-required",
    "python3 scripts/ci_container_runtime_proof.py capture .ci-runtime-proof/container.json",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
]
REQUIRED_EVIDENCE_DEPENDENCY = [
    "needs: container_bound",
    "runs-on: ubuntu-latest",
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
    "python3 scripts/ci_container_runtime_proof.py verify .ci-runtime-proof/container.json",
    "python3 scripts/test_evidence_dependency_graph.py",
    "go -C .atlas-core run ./cmd/atlas audit \"$PWD\" --gate evidence-dependency",
]
REQUIRED_DCO = [
    "scripts/verify_dco_range.py",
    "github.event.pull_request.base.sha",
    "github.event.before",
    ".atlas-core/scripts/check_dco.py",
]
ACTION_PINS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-go": "40f1582b2485089dde7abd97c1529aa768e1baff",
    "actions/setup-java": "cf277c60eb25467037889841efdb72551f06f6c3",
    "gradle/actions/setup-gradle": "ed408507eac070d1f99cc633dbcf757c94c7933a",
    "actions/setup-node": "49933ea5288caeca8642d1e84afbd3f7d6820020",
    "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
}


def split_jobs(text: str) -> tuple[str, str, str, str]:
    validate_marker = "  validate_bound:\n"
    container_marker = "  container_bound:\n"
    dependency_marker = "  evidence_dependency:\n"
    dco_marker = "  dco:\n"
    if validate_marker not in text or container_marker not in text or dependency_marker not in text or dco_marker not in text:
        raise RuntimeError("validate_bound/container_bound/evidence_dependency/dco Jobのいずれかがありません")
    before_container, after_container = text.split(container_marker, 1)
    validate = before_container.split(validate_marker, 1)[1]
    container, after_dependency = after_container.split(dependency_marker, 1)
    dependency, dco = after_dependency.split(dco_marker, 1)
    return validate, container, dependency, dco


def validate_workflow(text: str) -> None:
    validate, container, dependency, dco = split_jobs(text)
    missing = [token for token in REQUIRED_VALIDATE if token not in validate]
    missing.extend(token for token in REQUIRED_CONTAINER if token not in container)
    missing.extend(token for token in REQUIRED_EVIDENCE_DEPENDENCY if token not in dependency)
    missing.extend(token for token in REQUIRED_DCO if token not in dco)
    if missing:
        raise RuntimeError("CI required profile/runtime stepがありません: " + ", ".join(missing))
    if "python3 scripts/verify.py\n" in validate or "python3 scripts/verify.py --skip-container" not in validate:
        raise RuntimeError("macOS local Jobは--skip-container Profileでなければなりません")
    if "verify_python_dependency_contract.py --require-runtime\n" in validate or "--require-runtime --no-write --runtime-proof" not in validate:
        raise RuntimeError("CI Python runtime検証は追跡済み固定Evidenceを書き換えてはなりません")
    if "generate_evidence_dependency_graph.py" in text:
        raise RuntimeError("部分CI JobからEvidence Dependency Graphを再発行できません")
    for action, commit in ACTION_PINS.items():
        references = re.findall(rf"uses:\s+{re.escape(action)}@([^\s#]+)", text)
        if not references or any(reference != commit or not re.fullmatch(r"[0-9a-f]{40}", reference) for reference in references):
            raise RuntimeError(f"GitHub Actionがexact commitへ固定されていません: {action}")
    container_script = (ROOT / "scripts" / "container-verify.sh").read_text(encoding="utf-8")
    for token in ["docker run --rm --network=none"]:
        if token not in container_script:
            raise RuntimeError("単一Container runtime/live identity contractがありません: " + token)
    verify_source = VERIFY_SOURCE.read_text(encoding="utf-8")
    for token in [
        '"--profile", "skip-container"',
        'test_evidence_dependency_graph.py',
        'if not skip_container:',
    ]:
        if token not in verify_source:
            raise RuntimeError("skip-container committed Graph stale contractがありません: " + token)


def expect_rejection(identifier: str, text: str, expected: str) -> dict:
    try:
        validate_workflow(text)
    except RuntimeError as error:
        if expected not in str(error):
            raise RuntimeError(f"{identifier}の拒否理由が不一致: {error}") from error
        return {"id": identifier, "expected_rejection": expected, "result": "pass"}
    raise RuntimeError(f"CI negative fixtureが拒否されません: {identifier}")


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    validate_workflow(text)
    fixtures = []
    fixtures.append(expect_rejection(
        "required-container-job-missing",
        text.split("  container_bound:\n", 1)[0],
        "validate_bound/container_bound/evidence_dependency/dco Jobのいずれかがありません",
    ))
    fixtures.append(expect_rejection(
        "required-evidence-dependency-job-missing",
        text.split("  evidence_dependency:\n", 1)[0],
        "validate_bound/container_bound/evidence_dependency/dco Jobのいずれかがありません",
    ))
    fixtures.append(expect_rejection(
        "required-dco-job-missing",
        text.split("  dco:\n", 1)[0],
        "validate_bound/container_bound/evidence_dependency/dco Jobのいずれかがありません",
    ))
    fixtures.append(expect_rejection(
        "network-none-runtime-step-missing",
        text.replace("scripts/container-verify.sh", "scripts/removed-container-step.sh"),
        "CI required profile/runtime stepがありません",
    ))
    fixtures.append(expect_rejection(
        "partial-job-graph-publication",
        text.replace(
            "python3 scripts/test_evidence_dependency_graph.py",
            "python3 scripts/generate_evidence_dependency_graph.py\n          python3 scripts/test_evidence_dependency_graph.py",
        ),
        "部分CI JobからEvidence Dependency Graphを再発行できません",
    ))
    fixtures.append(expect_rejection(
        "container-job-graph-publication",
        text.replace(
            "run: scripts/container-verify.sh",
            "run: scripts/container-verify.sh && python3 scripts/generate_evidence_dependency_graph.py",
        ),
        "部分CI JobからEvidence Dependency Graphを再発行できません",
    ))
    fixtures.append(expect_rejection(
        "dependency-graph-live-audit-missing",
        text.replace("go -C .atlas-core run ./cmd/atlas audit \"$PWD\" --gate evidence-dependency", "go -C .atlas-core run ./cmd/atlas audit \"$PWD\" --gate removed"),
        "CI required profile/runtime stepがありません",
    ))
    fixtures.append(expect_rejection(
        "runtime-proof-transfer-missing",
        text.replace("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", "actions/removed-download@" + "1" * 40),
        "CI required profile/runtime stepがありません",
    ))
    fixtures.append(expect_rejection(
        "mutable-action-ref",
        text.replace("actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020", "actions/setup-node@v4"),
        "GitHub Actionがexact commitへ固定されていません",
    ))
    fixtures.append(expect_rejection(
        "python-runtime-mutates-static-evidence",
        text.replace("--require-runtime --no-write --runtime-proof", "--require-runtime"),
        "CI required profile/runtime stepがありません",
    ))
    fixtures.append(expect_rejection(
        "python-runtime-proof-missing",
        text.replace("python-dependency-runtime-${{ github.run_id }}-${{ github.run_attempt }}", "removed-python-runtime-proof"),
        "CI required profile/runtime stepがありません",
    ))

    with tempfile.TemporaryDirectory(prefix="kotlin-no-docker-path-") as raw:
        empty_path = str(Path(raw))
        with patch.dict(os.environ, {"PATH": empty_path}, clear=False), patch(
            "verify_evidence_dependency_profile.core_audit", return_value="fixture core audit pass"
        ):
            skip = verify("skip-container")
            if skip.get("verdict") != "pass" or skip.get("docker_invocation") != "forbidden-read-only":
                raise RuntimeError("Docker PATHなしskip-container profileがread-only passになりません")
            try:
                verify("container-required")
            except RuntimeError as error:
                if "Docker CLI" not in str(error):
                    raise
            else:
                raise RuntimeError("Docker PATHなしcontainer-required profileがfail-closedになりません")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "profile_split": {
            "macos": "real local/Native runtime; committed container Evidence is read-only and stale-checked",
            "ubuntu": "one network-none real container runtime with live Docker identity, followed by committed Graph read-only Core audit",
        },
        "docker_path_absence": {
            "skip_container": "pass",
            "container_required": "expected-failure",
        },
        "negative_fixtures": fixtures,
        "container_runtime_proof": "CI container_bound Job executes one scripts/container-verify.sh run, probes live Docker identity, performs committed Graph audit, and transfers a subject/input-bound proof to evidence_dependency",
        "dco_range": "fixed Core checker validates only explicit PR base..head or push before..sha new commits",
        "action_pins": ACTION_PINS,
        "python_dependency_evidence": "tracked contract Evidence is deterministic across host Python; pinned CPython 3.14 identity is emitted only to the same-job runtime Proof artifact",
        "graph_publication": "owner-managed full python3 scripts/verify.py only; partial CI jobs are read-only",
        "verdict": "pass",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"CI Profile contract passed: negative={len(fixtures)} docker-path=2")


if __name__ == "__main__":
    main()
