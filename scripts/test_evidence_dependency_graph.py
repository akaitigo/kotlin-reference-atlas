#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Core Evidence Dependency GateのKotlin固有negative fixture。"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from generate_evidence_dependency_graph import canonical, digest_bytes

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = "evidence/dependency-graph.json"
REPORT = ROOT / "evidence/artifacts/evidence-dependency-validation.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def aggregate(root: Path, members: list[str]) -> str:
    return digest_bytes(canonical([
        {"path": path, "digest": digest_bytes((root / path).read_bytes())}
        for path in sorted(members)
    ]))


def copy_fixture(root: Path, graph: dict) -> None:
    paths = {GRAPH_PATH, "definitive.yaml"}
    for item in graph["inputs"]:
        paths.update(item["members"])
    paths.update(item["path"] for item in graph["outputs"])
    for relative in sorted(paths):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def audit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / "bin/atlas"), "audit", str(root), "--gate", "evidence-dependency"],
        cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def update_output_digest(root: Path, graph: dict, relative: str) -> None:
    for item in graph["outputs"]:
        if item["path"] == relative:
            item["digest"] = digest_bytes((root / relative).read_bytes())
            return
    raise AssertionError(f"output not found: {relative}")


def expect_failure(identifier: str, base: Path, graph: dict, mutate, expected: str) -> dict:
    case = base.parent / identifier
    shutil.copytree(base, case)
    document = copy.deepcopy(graph)
    mutate(case, document)
    write(case / GRAPH_PATH, document)
    result = audit(case)
    passed = result.returncode != 0 and expected in result.stdout
    if not passed:
        raise RuntimeError(
            f"Evidence Dependency negative fixtureが期待拒否になりません: {identifier}\n"
            f"expected={expected!r}\noutput={result.stdout}"
        )
    return {"id": identifier, "result": "pass", "expected_rejection": expected}


def main() -> None:
    graph = load(ROOT / GRAPH_PATH)
    results = []
    with tempfile.TemporaryDirectory(prefix="kotlin-evidence-dependency-") as raw:
        temp = Path(raw)
        base = temp / "base"
        base.mkdir()
        copy_fixture(base, graph)
        positive = audit(base)
        if positive.returncode != 0:
            raise RuntimeError(f"Evidence Dependency positive fixtureが失敗しました:\n{positive.stdout}")

        def current_digest_mismatch(root: Path, document: dict) -> None:
            member = document["inputs"][0]["members"][0]
            with (root / member).open("ab") as handle:
                handle.write(b"\ninput-change")

        results.append(expect_failure(
            "input-change-stales-transitively", base, graph, current_digest_mismatch,
            "current_digestが実体と一致しません",
        ))

        def digest_only(root: Path, document: dict) -> None:
            changed = document["inputs"][0]
            member = changed["members"][0]
            with (root / member).open("ab") as handle:
                handle.write(b"\ndigest-only-change")
            changed["current_digest"] = aggregate(root, changed["members"])
            changed["observed_at"] = "2026-08-29T02:00:00+09:00"
            for binding in document["runs"][0]["input_bindings"]:
                if binding["input_id"] == changed["id"]:
                    binding["digest"] = changed["current_digest"]

        results.append(expect_failure(
            "digest-only-closure", base, graph, digest_only,
            "digest書換えだけではClosureできません",
        ))

        def missing_target(root: Path, document: dict) -> None:
            path = "evidence/scenarios/index.json"
            output = next(item for item in document["outputs"] if item["path"] == path)
            document["outputs"] = [item for item in document["outputs"] if item["id"] != output["id"]]
            document["required_outputs"] = [item for item in document["required_outputs"] if item != path]
            document["runs"][0]["output_ids"] = [item for item in document["runs"][0]["output_ids"] if item != output["id"]]

        results.append(expect_failure(
            "required-output-omission", base, graph, missing_target,
            "再実行対象がEvidence dependency graphから欠落しています",
        ))

        def retreated_output(root: Path, document: dict) -> None:
            document["outputs"][0]["status"] = "stale"

        results.append(expect_failure(
            "stale-output-retreat", base, graph, retreated_output,
            "影響Evidenceがstaleのままです",
        ))

        def no_identity(root: Path, document: dict) -> None:
            document["runs"][0].pop("runtime_identity")

        results.append(expect_failure(
            "runtime-identity-omission", base, graph, no_identity,
            "runtime_identityがありません",
        ))

        def retry_used(root: Path, document: dict) -> None:
            document["runs"][0]["attempts"] = 2

        results.append(expect_failure(
            "first-attempt-violation", base, graph, retry_used, "attempts",
        ))

        def proof_structure_shrink(root: Path, document: dict) -> None:
            relative = "evidence/scenarios/index.json"
            index = load(root / relative)
            index["denominator"] = "縮小されたdenominator"
            write(root / relative, index)
            update_output_digest(root, document, relative)

        results.append(expect_failure(
            "scenario-proof-structure-shrink", base, graph, proof_structure_shrink,
            "既存Proof/Closure Planの構造が変化しています",
        ))

        def closure_structure_shrink(root: Path, document: dict) -> None:
            relative = "evidence/scenarios/closure-plan.json"
            plan = load(root / relative)
            plan["scope"] = "縮小されたscope"
            write(root / relative, plan)
            update_output_digest(root, document, relative)

        results.append(expect_failure(
            "closure-plan-structure-shrink", base, graph, closure_structure_shrink,
            "既存Proof/Closure Planの構造が変化しています",
        ))

    write(REPORT, {
        "schema_version": 1,
        "atlas_id": "kotlin-reference-atlas",
        "gate": "evidence-dependency",
        "positive_fixture": "pass",
        "negative_fixtures": results,
        "non_regression_connection": "active Core baseline fixes the graph collection and structure fingerprints",
        "definitive_connection": "definitive.yaml requires evidence/dependency-graph.json",
        "certificate_connection": "Definitive certificate remains unavailable while repository status is incomplete",
        "verdict": "pass",
    })
    print(f"Evidence Dependency fixtures passed: positive=1 negative={len(results)}")


if __name__ == "__main__":
    main()
