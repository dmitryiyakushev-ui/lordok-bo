#!/usr/bin/env bash
# Деплой ЛОРдока: сервер забирает изменения из GitHub и пересобирает бота.
# Запускать с макбука из корня репозитория: bash ops/deploy.sh
#
# Никаких архивов и scp: на сервере лежит тот же репозиторий, обновление
# идёт только перемоткой вперёд. Если на сервере окажутся локальные
# правки, деплой остановится, а не затрёт их.
set -euo pipefail

SERVER="root@216.57.108.105"
REMOTE_DIR="/opt/lordok_bot"

echo "▶ Проверяю, что всё запушено"
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ Есть незакоммиченные изменения. Сначала коммит."
  exit 1
fi
git fetch --quiet origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "❌ Локальная ветка разошлась с origin/main. Сначала git push."
  exit 1
fi

echo "▶ Обновляю код на сервере"
ssh "$SERVER" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/lordok_bot

# Конфиг nginx общий для нескольких сайтов и в репозиторий не входит.
# Страховка на случай, если он когда-нибудь пропадёт с диска.
if [ ! -s site/nginx.conf ]; then
  echo "⚠️  site/nginx.conf пуст или отсутствует, достаю из контейнера"
  docker exec lordok_nginx cat /etc/nginx/conf.d/default.conf > site/nginx.conf
fi

git pull --ff-only --quiet origin main
echo "версия: $(git log --oneline -1)"

docker compose up -d --build bot
REMOTE

echo "▶ Жду подъёма и проверяю"
sleep 12
ssh "$SERVER" bash -s <<'REMOTE'
set -euo pipefail
errors=$(docker logs --since 2m lordok_bot 2>&1 | grep -ciE "error|traceback" || true)
echo "ошибок в логе за 2 минуты: $errors"
docker logs --since 2m lordok_bot 2>&1 | grep -E "Database initialized|Reminder scheduler started" | tail -2
/usr/bin/python3 /opt/pulsar/lordok_watchdog.py
REMOTE

echo "✅ Готово"
