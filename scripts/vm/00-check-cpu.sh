#!/usr/bin/env bash
# ==============================================================================
# 00-check-cpu.sh
# Phase 0 Gate Check: Verify PCLMULQDQ CPU instruction support
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [Phase 0 Gate] Checking CPU instruction support ===${NC}"

CPU_FLAGS="$(grep -m 1 '^flags' /proc/cpuinfo || true)"
MODEL_NAME="$(grep -m 1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs || true)"

echo "CPU Model: ${MODEL_NAME}"

if echo "${CPU_FLAGS}" | grep -q "pclmulqdq"; then
    echo -e "${GREEN}[OK] PCLMULQDQ instruction is supported.${NC}"
    echo "Antigravity CLI (agy) can safely run without SIGILL crash."
    exit 0
else
    echo -e "${RED}[ERROR] PCLMULQDQ instruction is NOT supported on this CPU!${NC}"
    echo -e "${YELLOW}Flags found: ${CPU_FLAGS}${NC}"
    echo ""
    echo "WARNING: Running agy on CPUs without pclmulqdq may cause SIGILL crashes."
    echo "Consider recreating the VM in another zone, choosing a different machine type, or switching to API key / hosted runner mode."
    exit 1
fi
