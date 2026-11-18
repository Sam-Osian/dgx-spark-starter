#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$ROOT/workspace"
for filename in prototype-notes.md results.csv; do
    if [[ ! -e "$ROOT/workspace/$filename" ]]; then
        cp "$ROOT/examples/$filename" "$ROOT/workspace/$filename"
    fi
done
echo 'Example notes and fictional CSV data are ready in workspace/.'
