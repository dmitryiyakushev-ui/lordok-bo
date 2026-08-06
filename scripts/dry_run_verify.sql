-- Post-migration verification.
-- Run AFTER the bot container has started at least once (so init_db +
-- run_runtime_migrations fired).
--
-- Expected outcome for the seeded legacy user (id=999000001):
--   1. patients row created with source='legacy_migration', needs_resolution=TRUE
--   2. users.active_patient_id points at that row
--   3. symptom_entries.patient_id is now populated
--   4. All new columns exist

\echo '── 1. New columns on users ──'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('full_name','phone','active_patient_id','nosology','age_group')
ORDER BY column_name;

\echo ''
\echo '── 2. New columns on symptom_entries ──'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'symptom_entries'
  AND column_name IN ('patient_id','user_id')
ORDER BY column_name;

\echo ''
\echo '── 3. patients table exists and has expected shape ──'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'patients'
ORDER BY ordinal_position;

\echo ''
\echo '── 4. Foreign keys on users.active_patient_id and symptom_entries.patient_id ──'
SELECT tc.table_name, tc.constraint_name, kcu.column_name,
       ccu.table_name AS references_table, ccu.column_name AS references_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('users','symptom_entries')
  AND kcu.column_name IN ('active_patient_id','patient_id')
ORDER BY tc.table_name;

\echo ''
\echo '── 5. Legacy backfill: the synthetic user (999000001) now has a Patient ──'
SELECT u.id AS user_id, u.first_name, u.active_patient_id,
       p.id AS patient_id, p.source, p.needs_resolution,
       p.relation, p.display_name, p.nosology, p.legacy_age_group, p.is_active
FROM users u
LEFT JOIN patients p ON p.user_id = u.id
WHERE u.id = 999000001;

\echo ''
\echo '── 6. Rewired symptom entries ──'
SELECT id, user_id, patient_id, nosology, recorded_at, triage_level
FROM symptom_entries
WHERE user_id = 999000001
ORDER BY recorded_at;

\echo ''
\echo '── 7. Sanity: any users with nosology set but no Patient row (should be 0) ──'
SELECT u.id, u.nosology
FROM users u
LEFT JOIN patients p ON p.user_id = u.id
WHERE u.nosology IS NOT NULL AND p.id IS NULL;
