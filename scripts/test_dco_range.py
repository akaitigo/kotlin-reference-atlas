#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""DCO range Gateの境界negative fixture。"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from verify_dco_range import ZERO_SHA, verify

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".atlas-core" / "scripts" / "check_dco.py"
REPORT = ROOT / "evidence" / "artifacts" / "dco-range-negative-tests.json"


def command(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, text=True, stdout=subprocess.PIPE)
    return result.stdout.strip()


def commit(root: Path, name: str, *, signed_off: bool) -> str:
    (root / name).write_text(name, encoding="utf-8")
    command(root, "add", name)
    message = f"test: {name}"
    if signed_off:
        message += "\n\nSigned-off-by: Kotlin Atlas CI <ci@example.invalid>"
    command(root, "commit", "-m", message)
    return command(root, "rev-parse", "HEAD")


def rejected(identifier: str, action, expected: str) -> dict:
    try:
        action()
    except RuntimeError as error:
        if expected not in str(error):
            raise RuntimeError(f"{identifier}の拒否理由が不一致: {error}") from error
        return {"id": identifier, "expected_rejection": expected, "result": "pass"}
    raise RuntimeError(f"DCO negative fixtureが拒否されません: {identifier}")


def main() -> None:
    if not CHECKER.is_file():
        raise RuntimeError("固定Core DCO checkerがありません")
    with tempfile.TemporaryDirectory(prefix="kotlin-dco-range-") as raw:
        repo = Path(raw)
        command(repo, "init")
        command(repo, "config", "user.name", "Kotlin Atlas CI")
        command(repo, "config", "user.email", "ci@example.invalid")
        base = commit(repo, "base", signed_off=True)
        signed = commit(repo, "signed", signed_off=True)
        if verify(repo, base, signed, CHECKER) != 1:
            raise RuntimeError("DCO positive fixtureのcommit数が不正")
        missing = commit(repo, "missing", signed_off=False)
        missing_result = rejected("missing-signoff", lambda: verify(repo, signed, missing, CHECKER), "Signed-off-by")
        mixed = rejected("mixed-signed-unsigned", lambda: verify(repo, base, missing, CHECKER), "Signed-off-by")
        command(repo, "checkout", "-b", "side", base)
        side = commit(repo, "side", signed_off=True)
        non_ancestor = rejected("non-ancestor", lambda: verify(repo, missing, side, CHECKER), "ancestor")
        empty = rejected("empty-range", lambda: verify(repo, signed, signed, CHECKER), "空")
        zero = rejected("zero-before", lambda: verify(repo, ZERO_SHA, signed, CHECKER), "非zero")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "positive_fixture": "pass",
        "negative_fixtures": [missing_result, mixed, non_ancestor, empty, zero],
        "legacy_history_policy": "only explicit base..head new commit range is checked",
        "verdict": "pass",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("DCO range fixtures passed: positive=1 negative=5")


if __name__ == "__main__":
    main()
