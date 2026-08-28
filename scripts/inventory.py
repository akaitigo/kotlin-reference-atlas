#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.4.10"
OUTPUT = ROOT / "atlas" / "inventory" / "kotlin-public-surface.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def locate(module: str, filename: str) -> Path:
    homes = [Path(os.environ.get("GRADLE_USER_HOME", ROOT / ".gradle" / "atlas-home")), Path.home() / ".gradle"]
    matches: list[Path] = []
    for home in homes:
        base = home / "caches" / "modules-2" / "files-2.1" / "org.jetbrains.kotlin" / module / VERSION
        if base.is_dir():
            matches.extend(base.glob(f"*/{filename}"))
    if not matches:
        raise FileNotFoundError(f"固定ArtifactがGradle cacheにありません: {module}:{VERSION}")
    return sorted(set(matches))[0]


def surface(path: Path, artifact: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        classes = sorted(name[:-6].replace("/", ".") for name in archive.namelist() if name.endswith(".class") and not name.endswith("module-info.class"))
    packages = sorted({name.rpartition(".")[0] for name in classes if "." in name})
    return {
        "artifact": artifact,
        "version": VERSION,
        "digest": digest(path),
        "class_count": len(classes),
        "package_count": len(packages),
        "packages": packages,
        "classes": classes,
    }


def main() -> None:
    stdlib = locate("kotlin-stdlib", f"kotlin-stdlib-{VERSION}.jar")
    compiler = locate("kotlin-compiler-embeddable", f"kotlin-compiler-embeddable-{VERSION}.jar")
    documents = [surface(stdlib, "org.jetbrains.kotlin:kotlin-stdlib"), surface(compiler, "org.jetbrains.kotlin:kotlin-compiler-embeddable")]
    compiler_classes = set(documents[1]["classes"])
    result = {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "epoch": "2026-08-28",
        "scope": "locked-artifact-class-and-package-surface",
        "language_feature_registry_class_present": "org.jetbrains.kotlin.config.LanguageFeature" in compiler_classes,
        "artifacts": documents,
        "verdict": "pass",
    }
    if not result["language_feature_registry_class_present"] or any(item["class_count"] == 0 for item in documents):
        raise RuntimeError("Compiler registryまたはClass inventoryが空です")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Inventory生成: {OUTPUT} classes={sum(item['class_count'] for item in documents)}")


if __name__ == "__main__":
    main()
