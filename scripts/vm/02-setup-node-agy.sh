#!/usr/bin/env bash
# ==============================================================================
# 02-setup-node-agy.sh
# Install Node.js LTS, Antigravity CLI (agy) fixed version, and configure environment
# ==============================================================================
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-runner}"
AGY_VERSION="${AGY_VERSION:-1.4.10}"
AGY_CLI_DISABLE_AUTO_UPDATE="${AGY_CLI_DISABLE_AUTO_UPDATE:-true}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [2/6] Installing Node.js & Antigravity CLI (${AGY_VERSION}) ===${NC}"

# 1. Create runner dedicated user if not exists
if ! id "${RUNNER_USER}" &>/dev/null; then
    echo "Creating dedicated user: ${RUNNER_USER}..."
    sudo useradd -m -s /bin/bash "${RUNNER_USER}"
else
    echo "User ${RUNNER_USER} already exists."
fi

# 2. Install Node.js LTS (v22 / v20) via NodeSource
if ! command -v node &>/dev/null; then
    echo "Installing Node.js LTS repository..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg --yes
    NODE_MAJOR=22
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
    sudo apt-get update -y
    sudo apt-get install -y nodejs
else
    echo "Node.js is already installed: $(node -v)"
fi

# 3. Install Antigravity CLI (agy)
echo "Installing @google/antigravity@${AGY_VERSION} globally..."
sudo npm install -g "@google/antigravity@${AGY_VERSION}"

# Verify installation
INSTALLED_AGY_VERSION="$(agy --version || true)"
echo "Installed agy version: ${INSTALLED_AGY_VERSION}"

# 4. Configure runner user environment variables and bashrc
RUNNER_HOME="$(eval echo ~${RUNNER_USER})"
RUNNER_BASHRC="${RUNNER_HOME}/.bashrc"

echo "Configuring environment variables for ${RUNNER_USER}..."

# Export AGY_CLI_DISABLE_AUTO_UPDATE to prevent unwanted updates
if ! grep -q "AGY_CLI_DISABLE_AUTO_UPDATE" "${RUNNER_BASHRC}"; then
    echo "export AGY_CLI_DISABLE_AUTO_UPDATE=${AGY_CLI_DISABLE_AUTO_UPDATE}" >> "${RUNNER_BASHRC}"
fi

# Dummy SSH_CONNECTION to enforce file-token OAuth flow
if ! grep -q "SSH_CONNECTION" "${RUNNER_BASHRC}"; then
    echo 'export SSH_CONNECTION="dummy 12345 127.0.0.1 22"' >> "${RUNNER_BASHRC}"
fi

# Global environment
if ! grep -q "AGY_CLI_DISABLE_AUTO_UPDATE" /etc/environment; then
    echo "AGY_CLI_DISABLE_AUTO_UPDATE=${AGY_CLI_DISABLE_AUTO_UPDATE}" | sudo tee -a /etc/environment
fi

# 5. Place default settings.json for runner user
RUNNER_AGY_DIR="${RUNNER_HOME}/.gemini/antigravity"
sudo -u "${RUNNER_USER}" mkdir -p "${RUNNER_AGY_DIR}"

SETTINGS_TEMPLATE="/tmp/settings.json"
if [ -f "${SETTINGS_TEMPLATE}" ]; then
    echo "Copying settings.json template to ${RUNNER_AGY_DIR}/settings.json..."
    sudo cp "${SETTINGS_TEMPLATE}" "${RUNNER_AGY_DIR}/settings.json"
    sudo chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_HOME}/.gemini"
    sudo chmod 600 "${RUNNER_AGY_DIR}/settings.json"
fi

echo -e "${GREEN}[OK] Node.js & agy installed successfully.${NC}"
