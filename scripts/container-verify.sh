#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
image="${ATLAS_CONTAINER_IMAGE:-kotlin-reference-atlas-verify:local}"

docker build --pull=false --tag "${image}" --file "${repo_root}/environments/container/Dockerfile" "${repo_root}"
docker run --rm --network=none "${image}"
