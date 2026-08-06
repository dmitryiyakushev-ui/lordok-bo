#!/usr/bin/env bash
# deploy_close_case.sh — Deploy "close case" feature to VPS
# Run from your Mac: bash deploy_close_case.sh
set -euo pipefail

VPS="root@5.42.101.251"
REMOTE="/opt/lordok_bot"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying 'close case' feature ==="

echo "[1/6] Uploading bot/models/patient.py (case_closed_at field) ..."
scp "$LOCAL/bot/models/patient.py" "$VPS:$REMOTE/bot/models/patient.py"

echo "[2/6] Uploading bot/db/runtime_migrations.py (ADD COLUMN) ..."
scp "$LOCAL/bot/db/runtime_migrations.py" "$VPS:$REMOTE/bot/db/runtime_migrations.py"

echo "[3/6] Uploading bot/keyboards/inline.py (close case button) ..."
scp "$LOCAL/bot/keyboards/inline.py" "$VPS:$REMOTE/bot/keyboards/inline.py"

echo "[4/6] Uploading bot/handlers/patients.py (close case handler) ..."
scp "$LOCAL/bot/handlers/patients.py" "$VPS:$REMOTE/bot/handlers/patients.py"

echo "[5/6] Uploading bot/handlers/log.py (is_first_visit + case_closed_at) ..."
scp "$LOCAL/bot/handlers/log.py" "$VPS:$REMOTE/bot/handlers/log.py"

echo "[6/6] Uploading bot/triage/params.py (first_visit_only flags) ..."
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
