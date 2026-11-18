#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash scripts/pull-models.sh [model ...]'
    echo 'Defaults: gemma4:e4b gemma4:26b (supports tool calling).'
    exit 0
fi
if ! command -v ollama >/dev/null; then
    echo 'Ollama is missing. Run bash scripts/setup.sh first.' >&2
    exit 1
fi
# ollama list/pull obey OLLAMA_HOST; the Python examples use OLLAMA_BASE_URL.
ready=0
for (( attempt=0; attempt<30; attempt++ )); do
    if ollama list >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
done
if (( ! ready )); then
    echo 'Ollama did not become ready. Check sudo systemctl status ollama' >&2
    echo 'or start ollama serve in another terminal; check OLLAMA_HOST if set.' >&2
    exit 1
fi
if (( $# == 0 )); then set -- gemma4:e4b gemma4:26b; fi
for model in "$@"; do
    echo "Downloading $model (existing blobs are reused)..."
    ollama pull "$model"
done
ollama list
