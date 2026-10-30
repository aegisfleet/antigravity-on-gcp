#!/usr/bin/env bash
# ==============================================================================
# 01-setup-os.sh
# System update, swap setup (2GB), and OS auto-update configuration
# ==============================================================================
set -euo pipefail

SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"
SWAP_FILE="/swapfile"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [1/6] Configuring OS and Swap ===${NC}"

# 1. Non-interactive apt configuration
export DEBIAN_FRONTEND=noninteractive

echo "Updating package list and upgrading installed packages..."
sudo apt-get update -y
sudo apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

echo "Installing essential packages..."
sudo apt-get install -y \
    curl \
    wget \
    git \
    jq \
    ripgrep \
    build-essential \
    ca-certificates \
    gnupg \
    unattended-upgrades \
    apt-listchanges

# 2. Swap configuration
if [ ! -f "${SWAP_FILE}" ]; then
    echo "Creating ${SWAP_SIZE_GB}GB swap file at ${SWAP_FILE}..."
    sudo fallocate -l "${SWAP_SIZE_GB}G" "${SWAP_FILE}" || sudo dd if=/dev/zero of="${SWAP_FILE}" bs=1M count=$((SWAP_SIZE_GB * 1024))
    sudo chmod 600 "${SWAP_FILE}"
    sudo mkswap "${SWAP_FILE}"
    sudo swapon "${SWAP_FILE}"
    if ! grep -q "${SWAP_FILE}" /etc/fstab; then
        echo "${SWAP_FILE} none swap sw 0 0" | sudo tee -a /etc/fstab
    fi
    echo -e "${GREEN}[OK] Swap file created and enabled.${NC}"
else
    echo "Swap file ${SWAP_FILE} already exists. Ensuring it is active..."
    sudo swapon "${SWAP_FILE}" 2>/dev/null || true
fi

# Swappiness optimization for e2-micro (1GB RAM)
if ! grep -q "vm.swappiness" /etc/sysctl.conf; then
    echo "vm.swappiness=20" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
fi

# 3. Enable unattended-upgrades
echo "Enabling unattended-upgrades..."
sudo systemctl enable unattended-upgrades
sudo systemctl start unattended-upgrades

echo -e "${GREEN}[OK] OS setup and swap configuration completed.${NC}"
free -h
