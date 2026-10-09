-- Run only against an isolated restored CRM snapshot.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';
-- Metadata only: no customer names, phones, VINs or other personal data.
SELECT table_name, column_name, data_type, udt_schema, udt_name, is_nullable,
       character_maximum_length, numeric_precision, datetime_precision,
       (column_default IS NOT NULL) AS has_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('customers', 'vehicles')
ORDER BY table_name, ordinal_position;

SELECT c.relname AS table_name, pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN ('customers','vehicles')
  AND c.relkind IN ('r','p')
ORDER BY c.relname;

-- Exact catalog definitions avoid incorrect pairing of composite foreign-key columns.
-- Run the entire audit through a read-only account/transaction in an isolated snapshot.
SELECT c.relname AS table_name, con.conname, con.contype,
       pg_get_constraintdef(con.oid, true) AS constraint_definition,
       con.condeferrable, con.condeferred, con.convalidated
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN ('customers', 'vehicles')
ORDER BY c.relname, con.conname;

SELECT c.relname AS table_name, a.attname AS column_name,
       a.attidentity AS identity_mode, a.attgenerated AS generated_mode,
       pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname) AS owned_sequence
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = 'public' AND c.relname IN ('customers', 'vehicles')
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum;

SELECT c.relname AS table_name, c.relkind, c.relrowsecurity, c.relforcerowsecurity,
       t.tgname AS trigger_name, t.tgenabled AS trigger_enabled,
       p.proname AS trigger_function
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_trigger t ON t.tgrelid = c.oid AND NOT t.tgisinternal
LEFT JOIN pg_proc p ON p.oid = t.tgfoid
WHERE n.nspname = 'public' AND c.relname IN ('customers', 'vehicles')
ORDER BY c.relname, t.tgname;

SELECT parent.relname AS parent_table, child.relname AS partition_table
FROM pg_inherits i JOIN pg_class parent ON parent.oid = i.inhparent
JOIN pg_class child ON child.oid = i.inhrelid
JOIN pg_namespace n ON n.oid = parent.relnamespace
WHERE n.nspname = 'public' AND parent.relname IN ('customers','vehicles')
ORDER BY parent.relname, child.relname;

-- Inbound references explain why a client-only archive cannot replace a full restore.
SELECT child.relname AS referencing_table, parent.relname AS client_table,
       con.conname, pg_get_constraintdef(con.oid, true) AS constraint_definition
FROM pg_constraint con
JOIN pg_class child ON child.oid = con.conrelid
JOIN pg_class parent ON parent.oid = con.confrelid
JOIN pg_namespace n ON n.oid = parent.relnamespace
WHERE con.contype = 'f' AND n.nspname = 'public'
  AND parent.relname IN ('customers','vehicles')
ORDER BY parent.relname, child.relname, con.conname;

SELECT tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname='public' AND tablename IN ('customers','vehicles')
ORDER BY tablename, indexname;

COMMIT;
