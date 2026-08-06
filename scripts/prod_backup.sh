#!/usr/bin/env bash
# Make a timestamped, compressed dump of the production ЛОРдок DB.
#
# Run on the VPS (5.42.101.251) from /opt/lordok_bot (or wherever compose lives).
# Keeps the DB online; read-only from pg_dump's perspective.
#
# Output: /opt/lordok_bot/backups/lordok_db_YYYYMMDD-HHMMSS.sql.gz

set -euo pipefail

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="/opt/lordok_bot/backups"
OUT="${BACKUP_DIR}/lordok_db_${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "→ Dumping lordok_db into ${OUT}"

# -Fp = plain SQL, works with psql for restore
docker compose exec -T postgres \
    pg_dump -U lordok -d lordok_db -Fp --clean --if-exists \
    | gzip -9 > "${OUT}"

SIZE=$(du -h "${OUT}" | awk '{print $1}')
echo "✓ Dump complete: ${OUT} (${SIZE})"

# Sanity: show newest 3 backups
echo "── Recent backups ──"
ls -lht "${BACKUP_DIR}" | head -n 5
