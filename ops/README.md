# Обвязка на сервере

## lordok_watchdog.py

Сторож бота. Лежит на сервере в `/opt/pulsar/lordok_watchdog.py`, копия
здесь для истории правок.

Проверяет каждые 15 минут:

- контейнер `lordok_bot` запущен;
- бот отвечает Telegram API (getMe его же токеном из `.env`);
- за последний час в логе меньше пяти фатальных ошибок.

При проблеме пишет в @pulsar_dy_bot один раз, повторных сообщений не
шлёт, пока состояние не изменится. Когда всё чинится, приходит
сообщение о восстановлении. Состояние в `/opt/pulsar/state/lordok_watchdog.json`.

Строка в cron:

```
*/15 * * * * /usr/bin/python3 /opt/pulsar/lordok_watchdog.py >> /opt/pulsar/logs/lordok_watchdog.log 2>&1
```

Токен для алёртов берётся из `/opt/pulsar/.env` (`PULSAR_BOT_TOKEN`,
`OWNER_TELEGRAM_ID`), токен бота из `/opt/lordok_bot/.env`. В репозитории
секретов нет.

## Осторожно: каталог site на сервере общий

`/opt/lordok_bot/site` это веб-корень nginx сразу для нескольких
проектов: lor-dok.ru, kod-03.ru, meduwiki.ru, calc, docs, pulsar и
n8n. В репозитории лежат только страницы ЛОРдока.

`site/nginx.conf` намеренно не под версией: он описывает все сайты
сразу, и деплой ЛОРдока перезаписывал бы конфигурацию соседей.
Живой конфиг всегда можно достать из контейнера:

```
docker exec lordok_nginx cat /etc/nginx/conf.d/default.conf
```
