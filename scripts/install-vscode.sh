#!/usr/bin/env bash
set -euo pipefail
if (( EUID == 0 )); then
    echo 'Run as your normal user, without sudo.' >&2
    exit 1
fi
if [[ $(uname -s) != Linux ]] || [[ $(dpkg --print-architecture) != arm64 ]]; then
    echo 'This installer requires Debian/Ubuntu Linux ARM64.' >&2
    exit 1
fi
if command -v code >/dev/null; then
    echo 'Reusing existing VS Code installation.'
    exit 0
fi
# The explicit ARM64 endpoint avoids the website choosing an x64 package.
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
chmod 755 "$temp"
curl --fail --show-error --location --retry 3 \
    https://update.code.visualstudio.com/latest/linux-deb-arm64/stable \
    -o "$temp/code-arm64.deb"
chmod 644 "$temp/code-arm64.deb"
if [[ $(dpkg-deb --field "$temp/code-arm64.deb" Architecture) != arm64 ]]; then
    echo 'Downloaded VS Code package has the wrong architecture.' >&2
    exit 1
fi
echo 'code code/add-microsoft-repo boolean true' | sudo debconf-set-selections
sudo apt-get install -y "$temp/code-arm64.deb"
echo 'Open VS Code with: code .'
