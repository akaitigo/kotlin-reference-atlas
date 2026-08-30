#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""新規commit rangeだけを固定Core DCO checkerへ渡す。"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ZERO_SHA = "0" * 40


def git(root: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=False, text=True,
        input=input_text, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def verify(root: Path, base: str, head: str, checker: Path) -> int:
    sha = re.compile(r"^[0-9a-fA-F]{40}$")
    if not sha.fullmatch(base) or base == ZERO_SHA:
        raise RuntimeError("DCO range baseは非zero 40桁SHAでなければなりません")
    if not sha.fullmatch(head) or head == ZERO_SHA:
        raise RuntimeError("DCO range headは非zero 40桁SHAでなければなりません")
    if base == head:
        raise RuntimeError("DCO rangeは空にできません")
    for name, revision in [("base", base), ("head", head)]:
        if git(root, "cat-file", "-e", revision + "^{commit}").returncode != 0:
            raise RuntimeError(f"DCO range {name} commitが存在しません")
    if git(root, "merge-base", "--is-ancestor", base, head).returncode != 0:
        raise RuntimeError("DCO range baseはheadのancestorではありません")
    records = git(root, "log", "--format=%H%x00%B%x00", f"{base}..{head}")
    if records.returncode != 0 or not records.stdout.strip("\0\n "):
        raise RuntimeError("DCO rangeに新規commitがありません")
    checked = subprocess.run(
        ["python3", str(checker)], cwd=root, check=False, text=True,
        input=records.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if checked.returncode != 0:
        raise RuntimeError(checked.stdout.strip() or "Core DCO checkerがrangeを拒否しました")
    return len([item for item in records.stdout.split("\0") if item.strip()]) // 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="新規commit rangeのDCOを検証する。")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--checker", type=Path, required=True)
    arguments = parser.parse_args()
    count = verify(arguments.repo_root, arguments.base, arguments.head, arguments.checker)
    print(f"DCO range Gate passed: commits={count} base={arguments.base} head={arguments.head}")
