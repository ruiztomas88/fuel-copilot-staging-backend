#!/bin/bash
# =============================================================================
# Daily Driver Score Snapshot Cron Job
# =============================================================================
# This script calls the /driver-scores/snapshot endpoint to save daily scores
# 
# SETUP:
# 1. Make executable: chmod +x /path/to/daily_driver_snapshot.sh
# 2. Add to crontab: crontab -e
# 3. Add line: 0 2 * * * /path/to/daily_driver_snapshot.sh >> /var/log/driver_snapshot.log 2>&1
#    (Runs at 2 AM daily)
#
# For systemd timer (alternative):
# See daily_driver_snapshot.timer and daily_driver_snapshot.service files
# =============================================================================

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ENDPOINT="/fuelAnalytics/api/analytics/driver-scores/snapshot"
LOG_PREFIX="[DRIVER_SNAPSHOT]"

# Get API key from environment or file
API_KEY="${FUEL_COPILOT_API_KEY:-}"
if [ -z "$API_KEY" ] && [ -f "/etc/fuel-copilot/api-key" ]; then
    API_KEY=$(cat /etc/fuel-copilot/api-key)
fi

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "${LOG_PREFIX} ${TIMESTAMP} - Starting daily driver score snapshot"

# Make the API call
RESPONSE=$(curl -s -X POST \
    "${API_BASE_URL}${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${API_KEY}" \
    -w "\n%{http_code}")

# Parse response
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "${LOG_PREFIX} ${TIMESTAMP} - SUCCESS: $BODY"
    exit 0
else
    echo "${LOG_PREFIX} ${TIMESTAMP} - FAILED (HTTP $HTTP_CODE): $BODY"
    exit 1
fi
