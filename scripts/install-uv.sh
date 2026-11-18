#!/usr/bin/env bash
# Install uv for the current user, without sudo.
set -euo pipefail
if (( EUID == 0 )); then
    echo 'Run as your normal user, without sudo.' >&2
    exit 1
fi
uv_bin_dir=${UV_INSTALL_DIR:-"$HOME/.local/bin"}
export PATH="$uv_bin_dir:$PATH"
if command -v uv >/dev/null; then
    echo 'Reusing existing uv installation.'
    uv --version
    exit 0
fi
if ! command -v curl >/dev/null; then
    echo 'curl is required to install uv. Install curl or run the full setup first.' >&2
    exit 1
fi
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
echo 'Downloading and running the official uv installer (no sudo).'
curl --fail --show-error --silent --location --retry 3 \
    https://astral.sh/uv/install.sh -o "$temp/uv-install.sh"
UV_INSTALL_DIR="$uv_bin_dir" sh "$temp/uv-install.sh"
"$uv_bin_dir/uv" --version
echo 'Open a new terminal to use uv, or add its install directory to PATH in this terminal:'
echo "  export PATH=\"$uv_bin_dir:\$PATH\""
