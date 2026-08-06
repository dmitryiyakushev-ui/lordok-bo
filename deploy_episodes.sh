#!/usr/bin/env bash
# deploy_episodes.sh — Deploy AOM/CRS episode counters to VPS
# Run from your Mac: bash deploy_episodes.sh
set -euo pipefail

VPS="root@5.42.101.251"
REMOTE="/opt/lordok_bot"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying episode counters update ==="

# 1. Copy modified files
echo "[1/4] Uploading bot/services/episodes.py ..."
scp "$LOCAL/bot/services/episodes.py" "$VPS:$REMOTE/bot/services/episodes.py"

echo "[2/4] Uploading bot/triage/params.py ..."
scp "$LOCAL/bot/triage/params.py" "$VPS:$REMOTE/bot/triage/params.py"

echo "[3/4] Uploading bot/handlers/log.py ..."
scp "$LOCAL/bot/handlers/log.py" "$VPS:$REMOTE/bot/handlers/log.py"

echo "[4/4] Uploading tests/test_episodes.py ..."
ssh "$VPS" "mkdir -p $REMOTE/tests"
scp "$LOCAL/tests/test_episodes.py" "$VPS:$REMOTE/tests/test_episodes.py"

# 2. Restart the bot
echo ""
echo "=== Restarting bot container ==="
ssh "$VPS" "cd $REMOTE && docker compose down && docker compose up -d --build"

# 3. Wait and check
echo ""
echo "=== Waiting 10s for bot to start ==="
sleep 10
ssh "$VPS" "cd $REMOTE && docker compose logs --tail=30 bot"

echo ""
echo "=== Done. Check logs above for errors. ==="
