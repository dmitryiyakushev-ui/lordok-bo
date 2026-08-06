#!/usr/bin/env bash
# deploy_pdf_report.sh — Deploy PDF report + history redirect to VPS
# Run from your Mac: bash deploy_pdf_report.sh
set -euo pipefail

VPS="root@5.42.101.251"
REMOTE="/opt/lordok_bot"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying PDF report update (with missing models) ==="

echo "[1/8] Uploading bot/models/scale_score.py ..."
scp "$LOCAL/bot/models/scale_score.py" "$VPS:$REMOTE/bot/models/scale_score.py"

echo "[2/8] Uploading bot/models/episode.py ..."
scp "$LOCAL/bot/models/episode.py" "$VPS:$REMOTE/bot/models/episode.py"

echo "[3/8] Uploading bot/models/__init__.py ..."
scp "$LOCAL/bot/models/__init__.py" "$VPS:$REMOTE/bot/models/__init__.py"

echo "[4/8] Uploading bot/utils/demographics.py ..."
ssh "$VPS" "mkdir -p $REMOTE/bot/utils"
scp "$LOCAL/bot/utils/demographics.py" "$VPS:$REMOTE/bot/utils/demographics.py"

echo "[5/10] Uploading bot/services/pdf_report.py ..."
scp "$LOCAL/bot/services/pdf_report.py" "$VPS:$REMOTE/bot/services/pdf_report.py"

echo "[6/10] Uploading bot/services/episodes.py ..."
scp "$LOCAL/bot/services/episodes.py" "$VPS:$REMOTE/bot/services/episodes.py"

echo "[7/10] Uploading bot/keyboards/inline.py ..."
scp "$LOCAL/bot/keyboards/inline.py" "$VPS:$REMOTE/bot/keyboards/inline.py"

echo "[8/10] Uploading bot/handlers/report.py ..."
scp "$LOCAL/bot/handlers/report.py" "$VPS:$REMOTE/bot/handlers/report.py"

echo "[9/10] Uploading bot/handlers/history.py ..."
scp "$LOCAL/bot/handlers/history.py" "$VPS:$REMOTE/bot/handlers/history.py"

echo "[10/10] Uploading bot/handlers/menu.py ..."
scp "$LOCAL/bot/handlers/menu.py" "$VPS:$REMOTE/bot/handlers/menu.py"

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
