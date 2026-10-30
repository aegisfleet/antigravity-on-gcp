#!/usr/bin/env bash
# ==============================================================================
# 05-setup-maintenance.sh
# Configure automated maintenance cron to prevent disk space exhaustion
# Cleans agy conversations, logs, and runner temp files older than 7 days
# ==============================================================================
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-runner}"
CLEANUP_SCRIPT="/usr/local/bin/agy-cleanup.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== [5/6] Setting up disk maintenance cron ===${NC}"

# Create cleanup script
sudo tee "${CLEANUP_SCRIPT}" > /dev/null << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

RUNNER_HOME="/home/runner"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"
echo "[${DATE}] Running agy maintenance cleanup..."

# 1. Clean agy conversation transcripts and brain logs older than 7 days
if [ -d "${RUNNER_HOME}/.gemini/antigravity/brain" ]; then
    find "${RUNNER_HOME}/.gemini/antigravity/brain" -mindepth 1 -maxdepth 2 -mtime +7 -exec rm -rf {} + 2>/dev/null || true
fi

# 2. Clean temporary files in runner work directories older than 3 days
find "${RUNNER_HOME}" -maxdepth 3 -type d -name "_work" -exec find {} -type f -mtime +3 -delete 2>/dev/null \; || true

# 3. Clean journal logs older than 7 days
journalctl --vacuum-time=7d >/dev/null 2>&1 || true

# 4. Clean apt cache
apt-get clean >/dev/null 2>&1 || true

echo "[${DATE}] agy maintenance cleanup completed."
EOF

sudo chmod +x "${CLEANUP_SCRIPT}"

# Add to crontab (runs daily at 03:00)
CRON_FILE="/etc/cron.d/agy-maintenance"
echo "0 3 * * * root ${CLEANUP_SCRIPT} >> /var/log/agy-cleanup.log 2>&1" | sudo tee "${CRON_FILE}" > /dev/null
sudo chmod 644 "${CRON_FILE}"

echo -e "${GREEN}[OK] Maintenance cron created at ${CRON_FILE}.${NC}"
