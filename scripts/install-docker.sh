#!/usr/bin/env bash
# Install Docker Engine and Compose on Ubuntu ARM64; run as a normal user.
set -euo pipefail
if (( EUID == 0 )); then
    echo 'Run as your normal user, without sudo.' >&2
    exit 1
fi
if [[ $(uname -s) != Linux || $(dpkg --print-architecture) != arm64 ]]; then
    echo 'Docker setup requires Ubuntu Linux ARM64.' >&2
    exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
codename=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
if [[ ${ID:-} != ubuntu && " ${ID_LIKE:-} " != *" ubuntu "* ]] || [[ -z "$codename" ]]; then
    echo 'Docker setup requires Ubuntu-based DGX OS with an Ubuntu release codename.' >&2
    exit 1
fi
installed() {
    [[ $(dpkg-query -W -f='${Status}' "$1" 2>/dev/null || true) == 'install ok installed' ]]
}
configure_repository() {
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl --fail --show-error --silent --location --retry 3 \
        https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $codename
Components: stable
Architectures: arm64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    sudo apt-get update
}

if command -v docker >/dev/null && docker --version >/dev/null 2>&1; then
    echo 'Reusing existing Docker installation.'
    if ! docker compose version >/dev/null 2>&1; then
        if installed docker.io; then
            sudo apt-get update
            sudo apt-get install -y docker-compose-v2
        elif installed docker-ce; then
            sudo apt-get update
            sudo apt-get install -y docker-compose-plugin
        else
            echo 'Install Compose using the same package source as your existing Docker installation.' >&2
            exit 1
        fi
    fi
else
    # Do not replace another application's container runtime automatically.
    for package in docker.io podman-docker containerd runc; do
        if installed "$package"; then
            echo "Existing $package package conflicts with Docker Engine. See https://docs.docker.com/engine/install/ubuntu/#uninstall-old-versions" >&2
            exit 1
        fi
    done
    configure_repository
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker.service
sudo docker info >/dev/null
docker compose version
echo 'Docker and Compose are ready. The browser startup script uses sudo when needed.'
