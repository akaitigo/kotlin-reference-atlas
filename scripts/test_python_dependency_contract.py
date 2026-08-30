#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Python dependency lockのmissing/tampered negative fixtureを検証する。"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from verify_python_dependency_contract import CONTRACT_PATH, ContractError, ROOT, validate_contract


def rejected(root: Path, expected: str) -> None:
    try:
        validate_contract(root, require_runtime=False, installed_version="6.0.3")
    except ContractError as error:
        if expected not in str(error):
            raise RuntimeError(f"negative fixtureが期待理由で拒否されない: {error}") from error
        return
    raise RuntimeError("negative fixtureが受理された")


def copy_contract(destination: Path) -> None:
    (destination / CONTRACT_PATH.parent).mkdir(parents=True)
    shutil.copy2(ROOT / CONTRACT_PATH, destination / CONTRACT_PATH)
    shutil.copy2(ROOT / "requirements-ci.lock", destination / "requirements-ci.lock")


def main() -> None:
    validate_contract(ROOT, require_runtime=False, installed_version="6.0.3")
    cases: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="kotlin-atlas-python-lock-") as directory:
        fixture = Path(directory)
        copy_contract(fixture)
        (fixture / "requirements-ci.lock").unlink()
        rejected(fixture, "requirements-ci.lockがない")
        cases.append({"id": "missing-requirements-lock", "expected": "reject", "verdict": "pass"})
    with tempfile.TemporaryDirectory(prefix="kotlin-atlas-python-lock-") as directory:
        fixture = Path(directory)
        copy_contract(fixture)
        lock = fixture / "requirements-ci.lock"
        lock.write_text(lock.read_text(encoding="utf-8").replace("34d5fcd2", "04d5fcd2", 1), encoding="utf-8")
        rejected(fixture, "digestが一致しない")
        cases.append({"id": "tampered-wheel-hash", "expected": "reject", "verdict": "pass"})
    with tempfile.TemporaryDirectory(prefix="kotlin-atlas-python-lock-") as directory:
        fixture = Path(directory)
        copy_contract(fixture)
        try:
            validate_contract(fixture, require_runtime=False, installed_version=None)
        except ContractError as error:
            if "実行PythonのPyYAML" not in str(error):
                raise
        else:
            raise RuntimeError("PyYAML missing fixtureが受理された")
        cases.append({"id": "missing-installed-pyyaml", "expected": "reject", "verdict": "pass"})
    report = {"schema_version": 1, "case_count": len(cases), "cases": cases, "verdict": "pass"}
    output = ROOT / "evidence" / "artifacts" / "python-dependency-negative-tests.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Python dependency negative test成功: cases={len(cases)}")


if __name__ == "__main__":
    main()
