#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / "labs" / "compiler-runtime" / "build" / "classes" / "kotlin" / "main"
OUTPUT = ROOT / "evidence" / "artifacts" / "bytecode-inspection.json"
TARGETS = [
    "dev.akaitigo.kotlinatlas.runtime.RuntimeRecord",
    "dev.akaitigo.kotlinatlas.runtime.RuntimeShapesKt",
]
TOKENS = ["component1", "copy", "kotlin.coroutines.Continuation", "capturedClosure", "filterRuntimeType"]


def main() -> None:
    javap = shutil.which("javap")
    if not javap:
        raise RuntimeError("JDK javapが見つかりません")
    completed = subprocess.run(
        [javap, "-classpath", str(CLASSES), "-p", "-c", "-s", *TARGETS],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    missing = [token for token in TOKENS if token not in completed.stdout]
    if missing:
        raise RuntimeError("javap必須Token不足: " + ",".join(missing))
    result = {
        "schema_version": 1,
        "tool": javap,
        "targets": TARGETS,
        "required_tokens": TOKENS,
        "missing_tokens": [],
        "output": completed.stdout,
        "verdict": "pass",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Bytecode検査: {len(TARGETS)} classes / {len(TOKENS)} tokens")


if __name__ == "__main__":
    main()
