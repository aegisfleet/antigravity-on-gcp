#!/usr/bin/env bash
# ==============================================================================
# 03-setup-gh.sh
# Install GitHub CLI (gh) via official apt repository
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [3/6] Installing GitHub CLI (gh) ===${NC}"

if ! command -v gh &>/dev/null; then
    echo "Adding GitHub CLI apt repository..."
    sudo mkdir -p -m 755 /etc/apt/keyrings
    wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y gh
else
    echo "GitHub CLI is already installed: $(gh --version | head -n 1)"
fi

echo -e "${GREEN}[OK] GitHub CLI is ready.${NC}"
