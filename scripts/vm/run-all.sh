#!/usr/bin/env bash
# ==============================================================================
# run-all.sh
# Execute VM base setup (00 through 03, and 05)
# Note: Runner setup (04) should be invoked per-repository with tokens.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Antigravity on GCP VM base provisioning..."

bash "${SCRIPT_DIR}/00-check-cpu.sh"
bash "${SCRIPT_DIR}/01-setup-os.sh"
bash "${SCRIPT_DIR}/02-setup-node-agy.sh"
bash "${SCRIPT_DIR}/03-setup-gh.sh"
bash "${SCRIPT_DIR}/05-setup-maintenance.sh"

echo ""
echo "=== Base VM setup completed successfully! ==="
