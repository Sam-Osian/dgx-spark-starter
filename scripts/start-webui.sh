#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v docker >/dev/null; then
    echo 'Docker is missing. Run bash scripts/setup.sh first.' >&2
    exit 1
fi
if docker info >/dev/null 2>&1; then
    docker_cmd=(docker)
else
    echo 'Docker requires sudo on this Spark. Enter your password if prompted.'
    docker_cmd=(sudo docker)
fi
"${docker_cmd[@]}" compose version >/dev/null
# Prepare the examples without overwriting files the user has changed.
bash "$ROOT/scripts/load-examples.sh"
# Keep a stable login secret outside Git; preserve it on subsequent starts.
mkdir -p "$ROOT/.local"
chmod 700 "$ROOT/.local"
if [[ ! -f "$ROOT/.local/webui.env" ]]; then
    (umask 077; python3 -c 'import secrets; print("WEBUI_SECRET_KEY=" + secrets.token_hex(32))' > "$ROOT/.local/webui.env")
fi
"${docker_cmd[@]}" compose -f "$ROOT/compose.yaml" up -d
echo 'Open http://localhost:8080 and create your local account, then select gemma4:26b.'
echo 'First startup may take a minute. Your chats persist between restarts.'
