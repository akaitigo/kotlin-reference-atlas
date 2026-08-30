#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CI Python/PyYAML lockを外部取得なしで検証する。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("toolchains/python-ci.lock.json")
EXPECTED_PYTHON = "3.14.0"
EXPECTED_PYYAML = "6.0.3"
EXPECTED_ACTION_COMMIT = "ece7cb06caefa5fff74198d8649806c4678c61a1"
HASH_PATTERN = re.compile(r"--hash=sha256:([0-9a-f]{64})")


class ContractError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def validate_static_report(report: dict) -> None:
    forbidden = {
        "observed_python",
        "runtime_version_required",
        "python_executable",
        "runner_os",
        "runner_arch",
        "github_run_id",
        "github_run_attempt",
    }
    leaked = sorted(forbidden.intersection(report))
    if leaked:
        raise ContractError("固定Dependency Evidenceへlive runtime fieldを保存できない: " + ", ".join(leaked))


def write_report(path: Path, report: dict) -> None:
    validate_static_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(report))


def installed_pyyaml_version() -> str | None:
    try:
        return importlib.metadata.version("PyYAML")
    except importlib.metadata.PackageNotFoundError:
        return None


def validate_contract(
    root: Path,
    *,
    require_runtime: bool,
    installed_version: str | None,
) -> dict:
    contract_file = root / CONTRACT_PATH
    if not contract_file.is_file():
        raise ContractError(f"Python dependency contractがない: {CONTRACT_PATH}")
    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("schema_versionは1でなければならない")
    python = contract.get("python", {})
    if python.get("implementation") != "CPython" or python.get("version") != EXPECTED_PYTHON:
        errors.append(f"CI PythonはCPython {EXPECTED_PYTHON}へ固定する")
    if python.get("setup_action") != "actions/setup-python" or python.get("setup_action_commit") != EXPECTED_ACTION_COMMIT:
        errors.append("actions/setup-pythonが許可commitへ固定されていない")
    packages = contract.get("packages", [])
    if len(packages) != 1:
        errors.append("CI Python package集合はlock済みPyYAML 1件でなければならない")
        package = {}
    else:
        package = packages[0]
    if package.get("distribution") != "PyYAML" or package.get("import_name") != "yaml" or package.get("version") != EXPECTED_PYYAML:
        errors.append(f"PyYAML {EXPECTED_PYYAML}のdistribution/import bindingがない")
    if package.get("license") != "MIT" or package.get("purl") != f"pkg:pypi/PyYAML@{EXPECTED_PYYAML}":
        errors.append("PyYAMLのrights/purl bindingが一致しない")
    requirements = contract.get("requirements", {})
    requirements_path = root / requirements.get("path", "")
    if requirements.get("path") != "requirements-ci.lock" or not requirements_path.is_file():
        errors.append("requirements-ci.lockがない")
        text = ""
    else:
        text = requirements_path.read_text(encoding="utf-8")
        if requirements.get("sha256") != sha256(requirements_path):
            errors.append("requirements-ci.lockのdigestが一致しない")
    if f"PyYAML=={EXPECTED_PYYAML}" not in text:
        errors.append(f"requirements-ci.lockがPyYAML=={EXPECTED_PYYAML}を固定していない")
    locked_hashes = set(HASH_PATTERN.findall(text))
    contract_hashes = set(package.get("wheel_sha256", []))
    if not locked_hashes or locked_hashes != contract_hashes:
        errors.append("requirementsとcontractのPyYAML wheel hash集合が一致しない")
    install_command = requirements.get("install_command", "")
    for token in ("--only-binary=:all:", "--require-hashes", "requirements-ci.lock"):
        if token not in install_command:
            errors.append(f"install commandに{token}がない")
    if installed_version != EXPECTED_PYYAML:
        errors.append(f"実行PythonのPyYAMLが{EXPECTED_PYYAML}ではない: {installed_version or 'missing'}")
    runtime_version = platform.python_version()
    if require_runtime and (platform.python_implementation() != "CPython" or runtime_version != EXPECTED_PYTHON):
        errors.append(f"CI runtimeはCPython {EXPECTED_PYTHON}でなければならない: {platform.python_implementation()} {runtime_version}")
    if errors:
        raise ContractError("; ".join(errors))
    return {
        "schema_version": 1,
        "profile_id": contract["profile_id"],
        "contract": CONTRACT_PATH.as_posix(),
        "contract_digest": sha256(contract_file),
        "requirements": requirements["path"],
        "requirements_digest": requirements["sha256"],
        "python": {"implementation": "CPython", "version": EXPECTED_PYTHON},
        "packages": [{"distribution": "PyYAML", "version": EXPECTED_PYYAML}],
        "python_contract_version": EXPECTED_PYTHON,
        "pyyaml_version": EXPECTED_PYYAML,
        "wheel_hash_count": len(locked_hashes),
        "verdict": "pass",
    }


def runtime_proof(static_report: dict) -> dict:
    validate_static_report(static_report)
    return {
        "schema_version": 1,
        "profile_id": static_report["profile_id"],
        "contract_evidence_digest": digest_bytes(canonical_bytes(static_report)),
        "observed_python": f"{platform.python_implementation()} {platform.python_version()}",
        "observed_pyyaml": installed_pyyaml_version(),
        "runner_os": platform.system(),
        "runner_arch": platform.machine(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
        "verdict": "pass",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-runtime", action="store_true", help="CIのPython patch versionも完全一致させる")
    parser.add_argument("--no-write", action="store_true", help="Evidence reportを書き換えない")
    parser.add_argument("--runtime-proof", type=Path, help="live runtime identityを追跡外のProfile Proofへ保存する")
    args = parser.parse_args()
    if args.runtime_proof is not None and not args.require_runtime:
        raise ContractError("runtime proof生成には--require-runtimeが必要")
    report = validate_contract(ROOT, require_runtime=args.require_runtime, installed_version=installed_pyyaml_version())
    if not args.no_write:
        output = ROOT / "evidence" / "artifacts" / "python-dependency-contract.json"
        write_report(output, report)
    if args.runtime_proof is not None:
        args.runtime_proof.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_proof.write_bytes(canonical_bytes(runtime_proof(report)))
    print(f"Python dependency contract成功: python={report['python_contract_version']} PyYAML={report['pyyaml_version']} hashes={report['wheel_hash_count']}")


if __name__ == "__main__":
    main()
