#!/usr/bin/env bash
# Read-only diagnostics. Does not load a model or install anything.
set -uo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="${UV_INSTALL_DIR:-"$HOME/.local/bin"}:$PATH"
failed=0
check() {
    local label=$1
    shift
    echo "--- $label"
    if ! "$@"; then failed=1; fi
}
check 'OS / architecture' uname -srm
check 'NVIDIA driver' nvidia-smi
check 'Ollama version' ollama --version
check 'Downloaded models' ollama list
check 'uv version' uv --version
check 'Project lockfile' uv lock --check --offline --project "$ROOT"
check 'Project Python dependencies' uv pip check --python "$ROOT/.venv/bin/python"
check 'Pydantic AI imports' "$ROOT/.venv/bin/python" -c \
    'from pydantic_ai import Agent, NativeOutput; from pydantic_ai.models.ollama import OllamaModel; print("OK")'
if command -v code >/dev/null; then check 'VS Code version' code --version; fi
echo '--- Disk space (model cache may be on a different filesystem)'
df -h "$ROOT" /usr/share/ollama 2>/dev/null || df -h "$ROOT"
echo '--- Loaded models and processor placement'
check 'ollama ps (empty is normal before first inference)' ollama ps
echo 'After running a demo, use ollama ps to verify GPU placement.'
echo 'If a check failed, see README troubleshooting. VS Code is optional.'
exit "$failed"
