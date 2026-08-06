#!/usr/bin/env bash
# deploy_bugfixes.sh — Fix: reminders not sending + duration asked on every visit
# Run from your Mac: bash deploy_bugfixes.sh
set -euo pipefail

VPS="root@5.42.101.251"
REMOTE="/opt/lordok_bot"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying bugfixes: reminders + duration skip ==="

echo "[1/5] Uploading bot/main.py (ReminderScheduler init) ..."
scp "$LOCAL/bot/main.py" "$VPS:$REMOTE/bot/main.py"

echo "[2/5] Uploading bot/services/scheduler.py ..."
scp "$LOCAL/bot/services/scheduler.py" "$VPS:$REMOTE/bot/services/scheduler.py"

echo "[3/5] Uploading bot/handlers/start.py (update_user_reminder call) ..."
scp "$LOCAL/bot/handlers/start.py" "$VPS:$REMOTE/bot/handlers/start.py"

echo "[4/5] Uploading bot/handlers/log.py (first_visit_only logic) ..."
scp "$LOCAL/bot/handlers/log.py" "$VPS:$REMOTE/bot/handlers/log.py"

echo "[5/5] Uploading bot/triage/params.py (first_visit_only flags) ..."
scp "$LOCAL/bot/triage/params.py" "$VPS:$REMOTE/bot/triage/params.py"

# Restart the bot
echo ""
echo "=== Restarting bot container ==="
ssh "$VPS" "cd $REMOTE && docker compose down && docker compose up -d --build"

# Wait and check
echo ""
echo "=== Waiting 10s for bot to start ==="
sleep 10
ssh "$VPS" "cd $REMOTE && docker compose logs --tail=30 bot"

echo ""
echo "=== Done. Check logs above for errors. ==="
