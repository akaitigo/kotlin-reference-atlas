#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""同一CI Jobの実Container runを後続read-only auditへdigest束縛する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUND_PATHS = [
    "scripts/container-verify.sh",
    "environments/container/Dockerfile",
    "evidence/dependency-graph.json",
]


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def docker_version() -> str:
    completed = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("実Docker server identityを取得できません")
    return completed.stdout.strip()


def capture(output: Path, *, environment: dict[str, str] | None = None, live_docker: str | None = None) -> dict:
    env = environment or os.environ
    required = ["GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError("CI runtime identityがありません: " + ", ".join(missing))
    document = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "execution_kind": "network-none-real-container-runtime",
        "command": "scripts/container-verify.sh",
        "subject_commit": env["GITHUB_SHA"],
        "github_run_id": env["GITHUB_RUN_ID"],
        "github_run_attempt": env["GITHUB_RUN_ATTEMPT"],
        "github_job": env["GITHUB_JOB"],
        "docker_server": live_docker or docker_version(),
        "first_attempt": env["GITHUB_RUN_ATTEMPT"] == "1",
        "input_bindings": [
            {"path": relative, "digest": digest(ROOT / relative)} for relative in BOUND_PATHS
        ],
        "graph_publication": "forbidden-in-ci-read-only",
        "verdict": "pass",
    }
    if not document["first_attempt"]:
        raise RuntimeError("Container Runtime Proofはfirst-attemptのみ受理します")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def verify(path: Path, *, environment: dict[str, str] | None = None) -> dict:
    env = environment or os.environ
    document = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if document.get("execution_kind") != "network-none-real-container-runtime":
        errors.append("execution_kind")
    if document.get("command") != "scripts/container-verify.sh":
        errors.append("command")
    if document.get("graph_publication") != "forbidden-in-ci-read-only":
        errors.append("graph_publication")
    if document.get("verdict") != "pass" or document.get("first_attempt") is not True:
        errors.append("verdict/first_attempt")
    expected_identity = {
        "subject_commit": env.get("GITHUB_SHA"),
        "github_run_id": env.get("GITHUB_RUN_ID"),
        "github_run_attempt": env.get("GITHUB_RUN_ATTEMPT"),
    }
    for key, expected in expected_identity.items():
        if not expected or document.get(key) != expected:
            errors.append(key)
    bindings = {item.get("path"): item.get("digest") for item in document.get("input_bindings", [])}
    for relative in BOUND_PATHS:
        if bindings.get(relative) != digest(ROOT / relative):
            errors.append("binding:" + relative)
    if not document.get("docker_server"):
        errors.append("docker_server")
    if errors:
        raise RuntimeError("CI Container Runtime Proof不整合: " + ", ".join(errors))
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CI Container Runtime Proofをcapture/verifyする。")
    parser.add_argument("mode", choices=["capture", "verify"])
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    result = capture(arguments.path) if arguments.mode == "capture" else verify(arguments.path)
    print(json.dumps({"mode": arguments.mode, "docker_server": result["docker_server"], "verdict": "pass"}, sort_keys=True))
