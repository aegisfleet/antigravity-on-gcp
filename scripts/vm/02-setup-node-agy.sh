#!/usr/bin/env bash
# ==============================================================================
# 02-setup-node-agy.sh
# Install Node.js LTS, Antigravity CLI (agy), and configure environment
# ==============================================================================
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-runner}"
AGY_CLI_DISABLE_AUTO_UPDATE="${AGY_CLI_DISABLE_AUTO_UPDATE:-true}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [2/6] Installing Node.js & Antigravity CLI (agy) ===${NC}"

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

# 3. Install Antigravity CLI (agy) via official installer
if ! command -v agy &>/dev/null; then
    echo "Downloading and installing Antigravity CLI (agy)..."
    curl -fsSL https://antigravity.google/cli/install.sh | bash
    if [ -f "$HOME/.local/bin/agy" ]; then
        sudo cp -f "$HOME/.local/bin/agy" /usr/local/bin/agy
        sudo chmod 755 /usr/local/bin/agy
    fi
else
    echo "Antigravity CLI is already installed: $(agy --version 2>/dev/null || true)"
fi

# Verify installation
INSTALLED_AGY_VERSION="$(agy --version 2>/dev/null || true)"
echo "Installed agy version: ${INSTALLED_AGY_VERSION}"

# 4. Configure runner user environment variables and bashrc
RUNNER_HOME="$(eval echo ~${RUNNER_USER})"
RUNNER_BASHRC="${RUNNER_HOME}/.bashrc"

echo "Configuring environment variables for ${RUNNER_USER}..."

# Export AGY_CLI_DISABLE_AUTO_UPDATE to prevent unwanted auto-updates during runs
if ! sudo grep -q "AGY_CLI_DISABLE_AUTO_UPDATE" "${RUNNER_BASHRC}" 2>/dev/null; then
    echo "export AGY_CLI_DISABLE_AUTO_UPDATE=${AGY_CLI_DISABLE_AUTO_UPDATE}" | sudo tee -a "${RUNNER_BASHRC}" > /dev/null
fi

# Dummy SSH_CONNECTION to enforce file-token OAuth flow
if ! sudo grep -q "SSH_CONNECTION" "${RUNNER_BASHRC}" 2>/dev/null; then
    echo 'export SSH_CONNECTION="dummy 12345 127.0.0.1 22"' | sudo tee -a "${RUNNER_BASHRC}" > /dev/null
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
