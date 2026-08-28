#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sbom.spdx.json"
THIRD_PARTY = ROOT / "third_party" / "manifest.yaml"
COORDINATE = re.compile(r"^([^:#=]+):([^:#=]+):([^=]+)=")


def spdx_id(kind: str, value: str) -> str:
    return f"SPDXRef-{kind}-{hashlib.sha256(value.encode()).hexdigest()[:20]}"


def gradle_components() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for lock in sorted(ROOT.rglob("gradle.lockfile")) + [ROOT / "settings-gradle.lockfile"]:
        if not lock.is_file() or "build" in lock.parts:
            continue
        for line in lock.read_text(encoding="utf-8").splitlines():
            match = COORDINATE.match(line)
            if not match:
                continue
            group, name, version = match.groups()
            key = f"pkg:maven/{group}/{name}@{version}"
            result[key] = {
                "name": f"{group}:{name}",
                "version": version,
                "purl": key,
                "ecosystem": "gradle",
                "license": maven_license(group),
            }
    return result


def maven_license(group: str) -> str:
    if group.startswith(("org.junit", "org.junit.jupiter", "org.junit.platform")):
        return "EPL-2.0"
    if group == "org.checkerframework":
        return "MIT"
    if group.startswith((
        "com.github.ben-manes.caffeine", "com.google.errorprone", "io.opentelemetry",
        "org.apiguardian", "org.jetbrains", "org.jetbrains.kotlin", "org.jetbrains.kotlinx",
        "org.opentest4j",
    )):
        return "Apache-2.0"
    raise RuntimeError(f"License mappingが未確定のMaven groupです: {group}")


def npm_components() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for lock in [ROOT / "kotlin-js-store" / "package-lock.json", ROOT / "kotlin-js-store" / "wasm" / "package-lock.json"]:
        document = json.loads(lock.read_text(encoding="utf-8"))
        for path, package in document.get("packages", {}).items():
            if not path or "node_modules/" not in path or "version" not in package:
                continue
            name = path.rsplit("node_modules/", 1)[1]
            version = package["version"]
            license_id = package.get("license")
            if not license_id and name.startswith("kotlin-reference-atlas-"):
                continue
            if not license_id:
                raise RuntimeError(f"Licenseが未確定のnpm packageです: {name}@{version}")
            key = f"pkg:npm/{name}@{version}"
            result[key] = {"name": name, "version": version, "purl": key, "ecosystem": "npm", "license": license_id}
    return result


def package(component: dict) -> dict:
    identity = component["purl"]
    return {
        "SPDXID": spdx_id("Package", identity),
        "name": component["name"],
        "versionInfo": component["version"],
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": component["license"],
        "licenseDeclared": component["license"],
        "copyrightText": "NOASSERTION",
        "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": identity}],
        "comment": f"{component['ecosystem']} lockから生成",
    }


def third_party_manifest(components: dict[str, dict]) -> dict:
    fixed = [
        {"id": "reference-atlas-core", "name": "reference-atlas-core", "kind": "source", "version": "eabefbb706c36140ae3f6509c9ca1bfae3c815ec", "source": "https://github.com/akaitigo/reference-atlas-core", "license": "Apache-2.0", "redistribution": "link-only"},
        {"id": "gradle-distribution", "name": "Gradle", "kind": "source", "version": "9.5.0", "source": "https://github.com/gradle/gradle", "license": "Apache-2.0", "redistribution": "link-only"},
        {"id": "nodejs-runtime", "name": "Node.js", "kind": "source", "version": "25.2.1", "source": "https://github.com/nodejs/node", "license": "MIT", "redistribution": "link-only"},
        {"id": "eclipse-temurin-runtime", "name": "Eclipse Temurin", "kind": "source", "version": "17", "source": "https://github.com/adoptium/temurin-build", "license": "GPL-2.0-with-classpath-exception", "redistribution": "link-only"},
    ]
    transitive = [
        {
            "id": "locked-" + hashlib.sha256(key.encode()).hexdigest()[:20],
            "name": component["name"],
            "kind": "maven-package" if component["ecosystem"] == "gradle" else "npm-package",
            "version": component["version"],
            "source": component["purl"],
            "license": component["license"],
            "redistribution": "metadata-only",
        }
        for key, component in sorted(components.items())
    ]
    return {"schema_version": 1, "artifacts": [*fixed, *transitive]}


def main() -> None:
    components = gradle_components()
    components.update(npm_components())
    root_package = {
        "SPDXID": "SPDXRef-Package-kotlin-reference-atlas",
        "name": "kotlin-reference-atlas",
        "versionInfo": "0.2.0",
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "Apache-2.0",
        "licenseDeclared": "Apache-2.0",
        "copyrightText": "Copyright 2026 Nakayama Ryusei",
    }
    packages = [root_package, *[package(components[key]) for key in sorted(components)]]
    closure = hashlib.sha256("\n".join(sorted(components)).encode()).hexdigest()
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "kotlin-reference-atlas-transitive-sbom",
        "documentNamespace": f"https://github.com/akaitigo/kotlin-reference-atlas/sbom/2026-08-28/{closure}",
        "creationInfo": {"created": "2026-08-28T00:00:00Z", "creators": ["Tool: scripts/generate_sbom.py"]},
        "documentDescribes": [root_package["SPDXID"]],
        "packages": packages,
        "relationships": [
            {"spdxElementId": root_package["SPDXID"], "relationshipType": "DEPENDS_ON", "relatedSpdxElement": item["SPDXID"]}
            for item in packages[1:]
        ],
        "annotations": [{
            "annotationDate": "2026-08-28T00:00:00Z",
            "annotationType": "OTHER",
            "annotator": "Tool: scripts/generate_sbom.py",
            "comment": f"Gradle/npm lock closure components={len(components)} sha256={closure}",
        }],
    }
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    THIRD_PARTY.write_text(json.dumps(third_party_manifest(components), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SPDX SBOM生成: components={len(components)} closure={closure}")


if __name__ == "__main__":
    main()
