# ЛОРдок — Telegram-бот мониторинга ЛОР-симптомов

Telegram-бот для ежедневного мониторинга симптомов хронических и острых ЛОР-заболеваний с rule-based триажем на основе международных клинических рекомендаций (AAO-HNS, EPOS 2020, IDSA, AAP).

## Стек

- Python 3.11, aiogram 3.13
- PostgreSQL 15, Redis 7
- SQLAlchemy 2.0 (async), Alembic
- ReportLab + matplotlib (PDF-отчёты)
- Docker Compose

## Быстрый старт

### 1. Создать Telegram-бота

- Открыть @BotFather → `/newbot` → получить токен
- Сохранить токен

### 2. Настроить окружение

```bash
cp .env.example .env
# Отредактировать .env — вписать BOT_TOKEN
```

### 3. Запустить

```bash
docker compose up -d
```

Это поднимет PostgreSQL, Redis и бота.

### 4. Применить миграции

```bash
docker compose exec bot alembic revision --autogenerate -m "Initial tables"
docker compose exec bot alembic upgrade head
```

### 5. Проверить

Открыть бота в Telegram → `/start`

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Онбординг: выбор нозологии, возраста, времени напоминания |
| `/log` | Заполнить дневник симптомов |
| `/history` | История записей (7 дней free, 30 дней premium) |
| `/report` | PDF-отчёт для врача (7/14/30 дней) |
| `/settings` | Изменить нозологию, возраст, напоминания |
| `/help` | Список команд |

## Нозологии

1. Острый риносинусит (AAO-HNS 2015, EPOS 2020)
2. Хронический риносинусит (EPOS 2020)
3. Острый тонзиллофарингит (IDSA 2012, McIsaac)
4. Острый средний отит (AAP/AAO-HNS 2013)
5. Хронический средний отит (AAO-HNS OME 2016)
6. Гипертрофия аденоидов (AAO-HNS 2019, AAP OSA 2012)

## Триаж

Трёхуровневая система:

- 🟢 **Наблюдайте** — стабильное/улучшающееся состояние
- 🟡 **Запишитесь к врачу** — ухудшение или настораживающая динамика
- 🔴 **Обратитесь сегодня** — красные флаги или выраженное ухудшение

Подробная документация decision tree: `clinical_decision_tree.md`

## Структура проекта

```
lordok_bot/
├── bot/
│   ├── main.py              # Точка входа
│   ├── config.py             # Настройки (Pydantic Settings)
│   ├── handlers/
│   │   ├── start.py          # /start, онбординг
│   │   ├── log.py            # /log, дневник симптомов
│   │   ├── history.py        # /history
│   │   ├── report.py         # /report (PDF)
│   │   └── common.py         # /help, /settings
│   ├── triage/
│   │   ├── engine.py         # Движок триажа
│   │   ├── red_flags.py      # Универсальные красные флаги
│   │   └── rules/            # Правила по нозологиям
│   │       ├── acute_rhinosinusitis.py
│   │       ├── chronic_rhinosinusitis.py
│   │       ├── acute_tonsillopharyngitis.py
│   │       ├── acute_otitis_media.py
│   │       ├── chronic_otitis_media.py
│   │       └── adenoid_hypertrophy.py
│   ├── models/
│   │   ├── user.py           # Модель пользователя
│   │   └── symptom.py        # Модель записи симптомов
│   ├── db/
│   │   ├── database.py       # SQLAlchemy async engine
│   │   └── migrations/       # Alembic
│   ├── services/
│   │   ├── pdf_report.py     # Генерация PDF
│   │   ├── charts.py         # Графики matplotlib
│   │   └── scheduler.py      # Напоминания (APScheduler)
│   └── keyboards/
│       └── inline.py         # Inline-клавиатуры
├── clinical_decision_tree.md  # Клиническая документация
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── .env.example
└── README.md
```

## Дисклеймер

ЛОРдок — информационный сервис для мониторинга симптомов.
Не является медицинским изделием.
Не предназначен для постановки диагноза или назначения лечения.
При ухудшении состояния всегда обращайтесь к врачу.
