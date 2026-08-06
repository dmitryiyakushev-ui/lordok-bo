#!/usr/bin/env bash
# Full deploy to VPS: bot code + static site (landing + legal docs) + nginx.
#
# Usage (on your Mac):
#   bash scripts/deploy_to_vps.sh
#
# Assumes:
#   - SSH key auth to root@5.42.101.251
#   - /opt/lordok_bot is the docker-compose root on the VPS
#
# What it does:
#   1. Creates a tarball of bot/, scripts/, site/, docker-compose.yml, .env, Dockerfile
#   2. Uploads it to the VPS
#   3. Backs up current state on the VPS
#   4. Extracts the tarball
#   5. Rebuilds bot container + starts nginx
#   6. Tails logs for verification

set -euo pipefail

VPS="root@5.42.101.251"
REMOTE_ROOT="/opt/lordok_bot"
STAMP=$(date -u +%Y%m%d-%H%M%S)
TARBALL="/tmp/lordok_deploy_${STAMP}.tar.gz"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${SCRIPT_DIR}"

echo "→ 1/6 Creating deploy tarball..."
tar -czf "${TARBALL}" \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    bot/ \
    scripts/ \
    site/ \
    docker-compose.yml \
    Dockerfile \
    requirements.txt \
    .env
echo "   ↳ $(du -h "${TARBALL}" | cut -f1) → ${TARBALL}"

echo "→ 2/6 Uploading to ${VPS}:${REMOTE_ROOT}/_incoming/"
ssh "${VPS}" "mkdir -p ${REMOTE_ROOT}/_incoming ${REMOTE_ROOT}/_backup"
scp "${TARBALL}" "${VPS}:${REMOTE_ROOT}/_incoming/deploy_${STAMP}.tar.gz"

echo "→ 3/6 Creating backup on VPS"
ssh "${VPS}" bash -s <<REMOTE
set -euo pipefail
cd ${REMOTE_ROOT}
[ -d bot ] && cp -r bot _backup/bot.bak.${STAMP}
[ -d site ] && cp -r site _backup/site.bak.${STAMP}
[ -d scripts ] && cp -r scripts _backup/scripts.bak.${STAMP}
[ -f docker-compose.yml ] && cp docker-compose.yml _backup/docker-compose.yml.bak.${STAMP}
echo "   ↳ backup saved to ${REMOTE_ROOT}/_backup/*bak.${STAMP}"
REMOTE

echo "→ 4/6 Extracting deploy tarball on VPS"
ssh "${VPS}" bash -s <<REMOTE
set -euo pipefail
cd ${REMOTE_ROOT}
tar -xzf _incoming/deploy_${STAMP}.tar.gz
echo "   ↳ files extracted:"
tar -tzf _incoming/deploy_${STAMP}.tar.gz | head -20
REMOTE

echo "→ 5/6 Rebuilding bot + starting nginx"
ssh "${VPS}" bash -s <<REMOTE
set -euo pipefail
cd ${REMOTE_ROOT}
docker compose up -d --build bot
docker compose up -d nginx
echo "   ↳ running containers:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
REMOTE

echo "→ 6/6 Tailing bot logs (15s)"
ssh "${VPS}" "cd ${REMOTE_ROOT} && timeout 15 docker compose logs -f --since 1m bot" || true

echo ""
echo "✓ Deploy finished."
echo "  Landing:  http://5.42.101.251/"
echo "  Privacy:  http://5.42.101.251/privacy.html"
echo "  Terms:    http://5.42.101.251/terms.html"
echo ""
echo "  Backup:   ${REMOTE_ROOT}/_backup/*bak.${STAMP}"
echo "  Rollback: ssh ${VPS} 'cd ${REMOTE_ROOT} && cp _backup/bot.bak.${STAMP} bot -r && cp _backup/site.bak.${STAMP} site -r && docker compose up -d --build bot && docker compose restart nginx'"

# Cleanup local tarball
rm -f "${TARBALL}"
