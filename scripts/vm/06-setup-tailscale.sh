#!/usr/bin/env bash
# ==============================================================================
# 06-setup-tailscale.sh (Optional)
# Install and configure Tailscale for secure mesh networking access
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [Optional] Installing Tailscale ===${NC}"

if ! command -v tailscale &>/dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${GREEN}[OK] Tailscale installed.${NC}"
    echo "To connect this VM to your Tailnet, run:"
    echo "  sudo tailscale up --ssh"
else
    echo "Tailscale is already installed."
    tailscale status || true
fi
