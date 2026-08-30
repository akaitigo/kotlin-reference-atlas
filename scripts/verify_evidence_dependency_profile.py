#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Evidence Dependency Graphの実行Profile境界を検証する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_COMMIT = "072d7ca77981f51754e824d70c6d4ecd55ea67e5"
GRAPH = ROOT / "evidence" / "dependency-graph.json"
CONTAINER_ARTIFACT = ROOT / "evidence" / "artifacts" / "container-verification.json"
CONTAINER_EVIDENCE = ROOT / "evidence" / "operation.container-verification.evidence.json"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_recorded_container_binding() -> dict:
    graph = load(GRAPH)
    artifact = load(CONTAINER_ARTIFACT)
    evidence = load(CONTAINER_EVIDENCE)
    errors: list[str] = []

    if artifact.get("verdict") != "pass":
        errors.append("committed container Evidenceがpassではない")
    if artifact.get("command") != "scripts/container-verify.sh":
        errors.append("committed container Evidenceの実行commandが不正")
    if artifact.get("network_disabled_on_replay") is not True:
        errors.append("committed container Evidenceがnetwork=noneを証明しない")
    if evidence.get("artifact", {}).get("uri") != "evidence/artifacts/container-verification.json":
        errors.append("container Evidence wrapperのartifact URIが不正")
    if evidence.get("artifact", {}).get("digest") != sha256(CONTAINER_ARTIFACT):
        errors.append("container Evidence wrapperのartifact digestが不一致")

    runs = graph.get("runs", [])
    if len(runs) != 1:
        errors.append("Evidence Dependency Graphのruntime runがexactly-oneではない")
    else:
        run = runs[0]
        identity = run.get("runtime_identity", {})
        if run.get("execution_kind") != "runtime" or run.get("result") != "passed" or run.get("attempts") != 1:
            errors.append("Evidence Dependency runが実runtime/first-attempt passではない")
        if identity.get("container_profile_command") != "scripts/container-verify.sh":
            errors.append("Graph runtime identityがcontainer commandへ束縛されていない")
        if identity.get("container_profile_dockerfile") != "environments/container/Dockerfile":
            errors.append("Graph runtime identityがDockerfileへ束縛されていない")
        if not identity.get("docker_server"):
            errors.append("Graph runtime identityに実Docker server identityがない")
        bindings = {item.get("input_id"): item.get("digest") for item in run.get("input_bindings", [])}
        for item in graph.get("inputs", []):
            if bindings.get(item.get("id")) != item.get("current_digest"):
                errors.append(f"Graph input bindingが現在digestと不一致: {item.get('id')}")

    if errors:
        raise RuntimeError("; ".join(errors))
    return {
        "graph_status": graph.get("status"),
        "container_artifact_digest": sha256(CONTAINER_ARTIFACT),
        "docker_server_identity": runs[0]["runtime_identity"]["docker_server"],
        "verdict": "pass",
    }


def require_live_docker() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise RuntimeError("container-required profileにはDocker CLIと実Docker runtimeが必要です")
    completed = subprocess.run(
        [executable, "version", "--format", "{{.Server.Version}}"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        raise RuntimeError("container-required profileで実Docker server identityを取得できません")
    return version


def core_audit() -> str:
    configured = os.environ.get("ATLAS_CORE_DIR")
    if configured:
        core_dir = Path(configured)
    elif (ROOT / ".atlas-core" / ".git").exists():
        core_dir = ROOT / ".atlas-core"
    else:
        core_dir = ROOT.parent / "reference-atlas-core"
    revision = subprocess.run(
        ["git", "-C", str(core_dir), "rev-parse", "HEAD"],
        cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if revision.returncode != 0 or revision.stdout.strip() != CORE_COMMIT:
        raise RuntimeError(
            f"固定Core commitを検証できません: expected={CORE_COMMIT} actual={revision.stdout.strip()}"
        )
    environment = os.environ.copy()
    environment["GOCACHE"] = str(ROOT / ".cache" / "go-build")
    (ROOT / ".cache" / "go-build").mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["go", "-C", str(core_dir), "run", "./cmd/atlas", "audit", str(ROOT), "--gate", "evidence-dependency"],
        cwd=ROOT,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise RuntimeError("committed Evidence Dependency Graphがstaleまたは不整合です:\n" + completed.stdout)
    return completed.stdout.strip()


def verify(profile: str, *, run_core_audit: bool = True) -> dict:
    recorded = validate_recorded_container_binding()
    live_docker = None
    if profile == "container-required":
        live_docker = require_live_docker()
    audit_output = core_audit() if run_core_audit else "fixtureではpure profile contractのみ検証"
    return {
        "profile": profile,
        "docker_invocation": "required-live" if profile == "container-required" else "forbidden-read-only",
        "live_docker_server": live_docker,
        "recorded_container": recorded,
        "core_audit": audit_output,
        "verdict": "pass",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evidence DependencyのProfile責務を検証する。")
    parser.add_argument("--profile", required=True, choices=["skip-container", "container-required"])
    parser.add_argument("--no-core-audit", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    result = verify(arguments.profile, run_core_audit=not arguments.no_core_audit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
