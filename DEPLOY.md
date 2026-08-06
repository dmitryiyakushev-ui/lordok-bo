# Деплой ЛОРдок на VPS — пошаговая инструкция

## 1. Выбрать и купить VPS

Любой российский провайдер. Подходящие варианты:

| Провайдер | Тариф | Цена | Ссылка |
|-----------|-------|------|--------|
| Timeweb Cloud | 1 vCPU, 2 GB RAM, 30 GB SSD | ~500 ₽/мес | cloud.timeweb.com |
| Selectel | Shared Line 1 vCPU, 2 GB | ~600 ₽/мес | selectel.ru |
| Beget | Cloud VPS S | ~400 ₽/мес | beget.com |

**Минимальные требования:** 1 vCPU, 2 GB RAM, 20 GB SSD, Ubuntu 22.04.

При создании сервера:
- Выбрать **Ubuntu 22.04 LTS**
- Включить SSH-доступ
- Записать **IP-адрес** и **root-пароль** (или SSH-ключ)

---

## 2. Подключиться к серверу

На Mac (Terminal уже есть):

```bash
ssh root@ТВОЙ_IP_АДРЕС
```

Ввести пароль, который дал провайдер. При первом подключении спросит про fingerprint — ввести `yes`.

---

## 3. Установить Docker (одна команда)

Скопировать и вставить в терминал целиком:

```bash
curl -fsSL https://get.docker.com | sh && systemctl enable docker && docker --version
```

Должно показать `Docker version 2X.X.X` — значит установлен.

---

## 4. Загрузить проект на сервер

**Вариант A — через git (рекомендуется):**

На сервере:
```bash
apt install -y git
cd /opt
git clone ТВОЙ_РЕПОЗИТОРИЙ lordok_bot
cd lordok_bot
```

**Вариант B — через scp (если без git):**

На своём Mac, из папки с проектом:
```bash
scp -r lordok_bot/ root@ТВОЙ_IP_АДРЕС:/opt/lordok_bot
```

Потом на сервере:
```bash
cd /opt/lordok_bot
```

---

## 5. Настроить окружение

```bash
cp .env.example .env
nano .env
```

Вписать токен бота (и другие настройки, если нужно). Сохранить: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

## 6. Запустить

```bash
docker compose up -d
```

Первый запуск займёт 2–5 минут (скачивание образов, сборка).

Проверить, что всё поднялось:
```bash
docker compose ps
```

Все три сервиса (bot, postgres, redis) должны быть в статусе `Up`.

---

## 7. Создать таблицы в базе данных

```bash
docker compose exec bot alembic revision --autogenerate -m "Initial tables"
docker compose exec bot alembic upgrade head
```

---

## 8. Проверить

Открыть Telegram → написать боту `/start`. Должен ответить приветствием и предложить выбрать нозологию.

---

## Полезные команды

```bash
# Посмотреть логи бота
docker compose logs -f bot

# Перезапустить бота (после изменений в коде)
docker compose restart bot

# Остановить всё
docker compose down

# Обновить код и перезапустить
cd /opt/lordok_bot
git pull
docker compose up -d --build

# Зайти в базу данных
docker compose exec postgres psql -U lordok -d lordok_db
```

---

## Безопасность (сделать после запуска)

```bash
# Создать отдельного пользователя (не работать под root)
adduser lordok
usermod -aG docker lordok

# Настроить файрвол
ufw allow 22/tcp    # SSH
ufw enable

# Сменить SSH-порт (опционально, снижает сканирование)
# nano /etc/ssh/sshd_config → Port 2222
# ufw allow 2222/tcp
# systemctl restart sshd
```

---

## Автозапуск после перезагрузки сервера

Docker Compose с `restart: unless-stopped` уже настроен — бот поднимется автоматически после перезагрузки VPS.

---

## Обновление до версии с закрытыми портами (август 2026)

До этой версии Postgres и Redis слушали 0.0.0.0 с паролем `lordok_secret`
прямо в docker-compose.yml. Обновление требует ручных шагов, иначе бот не
поднимется.

1. Придумать два новых пароля и дописать их в `.env` на сервере:

```bash
cd /opt/lordok_bot
echo "POSTGRES_PASSWORD=НОВЫЙ_ПАРОЛЬ_БАЗЫ" >> .env
echo "REDIS_PASSWORD=НОВЫЙ_ПАРОЛЬ_REDIS" >> .env
```

2. Сменить пароль у уже существующей базы. Переменная `POSTGRES_PASSWORD`
   действует только при первом создании тома, поэтому старую базу надо
   переключить вручную:

```bash
docker compose exec postgres psql -U lordok -d lordok_db -c "ALTER USER lordok WITH PASSWORD 'НОВЫЙ_ПАРОЛЬ_БАЗЫ';"
```

3. Поднять новую конфигурацию:

```bash
docker compose up -d --build
```

4. Убедиться, что снаружи порты закрыты (обе команды должны молчать или
   отваливаться по таймауту, запускать с другой машины):

```bash
nc -zv IP_СЕРВЕРА 5432
nc -zv IP_СЕРВЕРА 6379
```

5. Заодно закрыть их файрволом, чтобы не зависеть только от docker:

```bash
ufw deny 5432/tcp
ufw deny 6379/tcp
```

---

## Если что-то не работает

| Проблема | Решение |
|----------|---------|
| `docker compose` не найден | `apt install docker-compose-plugin` |
| Бот не отвечает | `docker compose logs bot` — смотреть ошибку |
| `connection refused` на PostgreSQL | Подождать 10 секунд, повторить (БД стартует дольше бота) |
| Мало памяти при сборке | Добавить swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
