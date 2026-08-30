#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CI Container Runtime Proofのtamper/missing/mismatch negative fixture。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ci_container_runtime_proof import capture, verify

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence" / "artifacts" / "ci-container-runtime-proof-negative-tests.json"
ENV = {
    "GITHUB_SHA": "a" * 40,
    "GITHUB_RUN_ID": "12345",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_JOB": "container",
}


def rejected(identifier: str, action) -> dict:
    try:
        action()
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError):
        return {"id": identifier, "result": "pass"}
    raise RuntimeError(f"Container Runtime Proof negative fixtureが拒否されません: {identifier}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="kotlin-ci-container-proof-") as raw:
        root = Path(raw)
        proof = root / "proof.json"
        capture(proof, environment=ENV, live_docker="fixture-docker-1")
        verify(proof, environment=ENV)
        base = json.loads(proof.read_text(encoding="utf-8"))
        results = [rejected("missing-proof", lambda: verify(root / "missing.json", environment=ENV))]

        tampered = root / "tampered.json"
        document = dict(base)
        document["docker_server"] = ""
        tampered.write_text(json.dumps(document), encoding="utf-8")
        results.append(rejected("missing-live-identity", lambda: verify(tampered, environment=ENV)))

        mismatched = root / "mismatched.json"
        document = dict(base)
        document["subject_commit"] = "b" * 40
        mismatched.write_text(json.dumps(document), encoding="utf-8")
        results.append(rejected("subject-mismatch", lambda: verify(mismatched, environment=ENV)))

        stale = root / "stale.json"
        document = json.loads(json.dumps(base))
        document["input_bindings"][0]["digest"] = "sha256:" + "0" * 64
        stale.write_text(json.dumps(document), encoding="utf-8")
        results.append(rejected("input-binding-tamper", lambda: verify(stale, environment=ENV)))

        retry_env = dict(ENV, GITHUB_RUN_ATTEMPT="2")
        results.append(rejected(
            "retry-capture",
            lambda: capture(root / "retry.json", environment=retry_env, live_docker="fixture-docker-1"),
        ))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "positive_fixture": "pass",
        "negative_fixtures": results,
        "verdict": "pass",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"CI Container Runtime Proof fixtures passed: positive=1 negative={len(results)}")


if __name__ == "__main__":
    main()
