-- Seed a legacy user + a legacy symptom entry BEFORE running the bot container.
-- Purpose: verify that runtime_migrations backfills a Patient row and rewires
-- the symptom_entries.patient_id.
--
-- Run this on a clean local test DB *before* starting the bot, e.g.:
--   docker compose up -d postgres
--   docker compose exec -T postgres psql -U lordok -d lordok_db \
--       < scripts/dry_run_legacy_seed.sql
--
-- NB: This requires the OLD schema to exist (the one before this refactor).
-- If you're seeding into a fresh DB created by the NEW schema, uncomment the
-- DDL block below — create_all() will already have added the new columns,
-- so the seed below is compatible.

BEGIN;

-- Minimal legacy user (old-style: nosology + age_group set on users).
-- Telegram user_id is a BigInteger; using a clearly-synthetic value.
INSERT INTO users (
    id, username, first_name, language_code,
    nosology, age_group,
    reminder_time, is_premium, created_at, updated_at
) VALUES (
    999000001, 'legacy_test', 'Старый Пользователь', 'ru',
    'ars', '15-44y',
    '20:00:00', FALSE, NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;

-- One legacy symptom entry tied only to user_id (patient_id still NULL).
INSERT INTO symptom_entries (
    user_id, nosology, recorded_at,
    symptoms, composite_score, triage_level, triage_message, red_flags
) VALUES (
    999000001, 'ars', NOW() - INTERVAL '2 days',
    '{"ars_obstruction": 2, "ars_facial_pain": 2, "ars_discharge": 1, "ars_temp": 1}'::jsonb,
    6, 'green', 'Legacy entry — pre-migration', '[]'::jsonb
);

COMMIT;
