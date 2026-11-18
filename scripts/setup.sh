#!/usr/bin/env bash
# Run as your normal user; sudo is used only for system installation.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
vscode=1
models=1
ollama_install=1
python_only=0
usage() {
    cat <<'EOF'
Usage: bash scripts/setup.sh [options]
  --skip-vscode   Skip VS Code installation (e.g. use Remote SSH)
  --skip-models   Skip all model downloads
  --skip-ollama   Use an existing Ollama installation/server
  --python-only  Only create/update the project Python environment; no sudo
  -h, --help     Show this help

Default models: gemma4:e4b and gemma4:26b. Existing Ollama and VS Code
installations are reused. No system-wide upgrade or driver install is run.
EOF
}
for arg in "$@"; do
    case "$arg" in
        --skip-vscode) vscode=0 ;;
        --skip-models) models=0 ;;
        --skip-ollama) ollama_install=0 ;;
        --python-only) python_only=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done
if (( EUID == 0 )); then
    echo 'Run this as your normal user, without sudo.' >&2
    exit 1
fi
if (( ! python_only )); then
    if [[ $(uname -s) != Linux || $(uname -m) != aarch64 ]]; then
        echo 'System setup requires Linux ARM64 (aarch64), as used by DGX Spark.' >&2
        exit 1
    fi
    if [[ ! -f /etc/debian_version ]] || ! command -v apt-get >/dev/null; then
        echo 'System setup requires an Ubuntu/Debian-based DGX OS installation.' >&2
        exit 1
    fi
    if (( ollama_install )); then
        # The upstream installer may try to install drivers if these are absent.
        # Spark drivers should be maintained using NVIDIA's DGX OS tools instead.
        if ! command -v nvidia-smi >/dev/null || ! nvidia-smi | grep -q 'CUDA Version:'; then
            echo 'A working NVIDIA driver is required. Fix/update DGX OS, reboot, and retry.' >&2
            exit 1
        fi
    fi
    sudo -v
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl git python3 python3-venv zstd pciutils
    if (( ollama_install )); then
        if ! command -v ollama >/dev/null; then
            temp=$(mktemp -d)
            trap 'rm -rf -- "$temp"' EXIT
            echo 'Downloading and running the official Ollama installer (uses sudo).'
            curl --fail --show-error --silent --location --retry 3 \
                https://ollama.com/install.sh -o "$temp/ollama-install.sh"
            sh "$temp/ollama-install.sh"
        else
            echo 'Reusing existing Ollama installation.'
        fi
        if systemctl cat ollama.service >/dev/null 2>&1; then
            sudo systemctl enable --now ollama.service
        else
            echo 'No Ollama systemd service found. Start ollama serve in another terminal.'
        fi
    fi
    if (( vscode )); then
        bash "$ROOT/scripts/install-vscode.sh"
    fi
fi
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --require-hashes -r "$ROOT/requirements.txt"
if (( ! python_only && models )); then
    bash "$ROOT/scripts/pull-models.sh" gemma4:e4b gemma4:26b
fi
echo 'Python environment ready. Try:'
echo "  cd \"$ROOT\""
echo '  .venv/bin/python examples/local_agent.py chat "Explain what a local LLM is."'
echo '  bash scripts/doctor.sh'
