#!/usr/bin/env bash
# ==============================================================================
# 04-setup-runner.sh
# Download, configure and install GitHub Actions Runner as a systemd service
# Usage:
#   sudo ./04-setup-runner.sh <owner/repo> <runner_registration_token> [runner_name]
# ==============================================================================
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-runner}"
REPO="${1:-}"
TOKEN="${2:-}"
RUNNER_NAME="${3:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ -z "${REPO}" ]; then
    echo -e "${RED}[ERROR] Repository not specified. Usage: $0 <owner/repo> <registration_token>${NC}"
    exit 1
fi

if [ -z "${TOKEN}" ]; then
    echo -e "${YELLOW}Please enter GitHub Actions Runner Registration Token for ${REPO}:${NC}"
    read -r -s TOKEN
    echo ""
    if [ -z "${TOKEN}" ]; then
        echo -e "${RED}[ERROR] Registration token cannot be empty.${NC}"
        exit 1
    fi
fi

REPO_SLUG="$(echo "${REPO}" | tr '/' '-')"
RUNNER_DIR="/home/${RUNNER_USER}/actions-runner-${REPO_SLUG}"

if [ -z "${RUNNER_NAME}" ]; then
    RUNNER_NAME="gcp-e2-micro-${REPO_SLUG}"
fi

echo -e "${CYAN}=== Setting up GitHub Actions Runner for ${REPO} ===${NC}"
echo "Target Directory: ${RUNNER_DIR}"
echo "Runner Name:      ${RUNNER_NAME}"

# 1. Ensure runner user exists
if ! id "${RUNNER_USER}" &>/dev/null; then
    sudo useradd -m -s /bin/bash "${RUNNER_USER}"
fi

# 2. Prepare directory
sudo mkdir -p "${RUNNER_DIR}"
sudo chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

# 3. Download runner package if not already downloaded
if [ ! -f "config.sh" ]; then
    echo "Fetching latest runner version..."
    RUNNER_VERSION="$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')"
    if [ -z "${RUNNER_VERSION}" ] || [ "${RUNNER_VERSION}" = "null" ]; then
        RUNNER_VERSION="2.322.0"
    fi
    RUNNER_ARCH="x64"
    TAR_NAME="actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
    DOWNLOAD_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${TAR_NAME}"

    echo "Downloading ${DOWNLOAD_URL}..."
    sudo -u "${RUNNER_USER}" curl -o "${TAR_NAME}" -L "${DOWNLOAD_URL}"
    sudo -u "${RUNNER_USER}" tar xzf "./${TAR_NAME}"
    sudo -u "${RUNNER_USER}" rm -f "./${TAR_NAME}"
fi

# 4. Install runner dependencies
if [ -f "bin/installdependencies.sh" ]; then
    sudo ./bin/installdependencies.sh
fi

# 5. Stop and uninstall existing service if present
if [ -f ".service" ]; then
    echo "Stopping existing runner service..."
    sudo ./svc.sh stop 2>/dev/null || true
    sudo ./svc.sh uninstall 2>/dev/null || true
fi

# 6. Configure runner
echo "Configuring runner for https://github.com/${REPO}..."
sudo -u "${RUNNER_USER}" ./config.sh \
    --url "https://github.com/${REPO}" \
    --token "${TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "self-hosted,e2-micro,agy" \
    --unattended \
    --replace

# 7. Install and start systemd service
echo "Installing and starting systemd service..."
sudo ./svc.sh install "${RUNNER_USER}"
sudo ./svc.sh start
sudo ./svc.sh status

echo -e "${GREEN}[OK] Runner for ${REPO} installed and started successfully!${NC}"
