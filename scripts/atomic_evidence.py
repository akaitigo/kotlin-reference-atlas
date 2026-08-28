#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable


class EvidencePublishError(RuntimeError):
    pass


def publish_directory(
    output_root: Path,
    build: Callable[[Path], None],
    validate: Callable[[Path], None],
    *,
    full_run_passed: bool,
    fault: str | None = None,
) -> bool:
    """Publish one complete Evidence generation or retain the previous generation.

    The output directory is the atomic unit. Build and validation happen in a
    sibling staging directory. A failed run never enters the swap phase. If the
    directory rename fails after the previous generation was retained, rollback
    restores it before the error is reported.
    """
    parent = output_root.parent
    staging = parent / f".{output_root.name}-next"
    backup = parent / f".{output_root.name}-previous"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        build(staging)
        if fault == "build":
            raise EvidencePublishError("injected build failure")
        validate(staging)
        if fault == "validate":
            raise EvidencePublishError("injected validation failure")
        if not full_run_passed:
            raise EvidencePublishError("full run did not pass; prior successful Evidence retained")
        shutil.rmtree(backup, ignore_errors=True)
        retained_previous = False
        try:
            if output_root.exists():
                os.replace(output_root, backup)
                retained_previous = True
            if fault == "swap":
                raise EvidencePublishError("injected swap failure")
            os.replace(staging, output_root)
        except Exception:
            if retained_previous:
                if output_root.exists():
                    shutil.rmtree(output_root)
                os.replace(backup, output_root)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return True
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
