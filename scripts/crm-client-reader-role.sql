-- Explicitly requested catalog change ONLY. Never edits CRM table rows or PUBLIC ACLs.
-- psql -X -v ON_ERROR_STOP=1 -v expected_database=EXACT_DB_NAME \
--   -v reader_role_install=REVIEWED_ROLE_ONLY -f scripts/crm-client-reader-role.sql
-- This session installs it only in a disposable crm_test_* database.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
SELECT set_config('client_backup.expected_database', :'expected_database', true);
SELECT set_config('client_backup.role_install', :'reader_role_install', true);
DO $guard$
BEGIN
 IF current_database() <> current_setting('client_backup.expected_database')
    OR current_setting('client_backup.role_install') <> 'REVIEWED_ROLE_ONLY' THEN
  RAISE EXCEPTION 'ROLE_INSTALL_TARGET_UNCONFIRMED';
 END IF;
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='crm_clients_backup_reader') THEN
  RAISE EXCEPTION 'EXISTING_ROLE_REFUSED';
 END IF;
 IF pg_get_serial_sequence('public.customers','id') IS DISTINCT FROM 'public.customers_id_seq'
    OR pg_get_serial_sequence('public.vehicles','id') IS DISTINCT FROM 'public.vehicles_id_seq' THEN
  RAISE EXCEPTION 'UNREVIEWED_SEQUENCE';
 END IF;
END $guard$;
-- No password is generated or included. Remote password login is unusable until
-- a trusted owner sets a password with psql \password, outside logs/history.
CREATE ROLE crm_clients_backup_reader LOGIN PASSWORD NULL
 NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
 CONNECTION LIMIT 2;
ALTER ROLE crm_clients_backup_reader SET default_transaction_read_only=on;
ALTER ROLE crm_clients_backup_reader SET statement_timeout='5min';
ALTER ROLE crm_clients_backup_reader SET lock_timeout='10s';
ALTER ROLE crm_clients_backup_reader SET search_path=pg_catalog,public;
SELECT format('GRANT CONNECT ON DATABASE %I TO crm_clients_backup_reader',current_database()) \gexec
GRANT USAGE ON SCHEMA public TO crm_clients_backup_reader;
GRANT SELECT ON TABLE public.customers,public.vehicles TO crm_clients_backup_reader;
GRANT SELECT ON SEQUENCE public.customers_id_seq,public.vehicles_id_seq TO crm_clients_backup_reader;
-- PUBLIC grants cannot be negated per role. Fail closed; never change shared ACLs.
DO $audit$
DECLARE unsafe_count bigint;
BEGIN
 SELECT count(*) INTO unsafe_count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
   AND c.relkind IN ('r','p','v','m','f')
   AND ((c.oid NOT IN ('public.customers'::regclass,'public.vehicles'::regclass)
         AND has_table_privilege('crm_clients_backup_reader',c.oid,'SELECT'))
        OR has_table_privilege('crm_clients_backup_reader',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'));
 IF unsafe_count<>0 THEN RAISE EXCEPTION 'UNSAFE_PUBLIC_TABLE_PRIVILEGES'; END IF;
 IF EXISTS(SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE c.relkind='S' AND n.nspname NOT LIKE 'pg_%'
           AND (has_sequence_privilege('crm_clients_backup_reader',c.oid,'USAGE,UPDATE')
                OR (c.oid NOT IN ('public.customers_id_seq'::regclass,'public.vehicles_id_seq'::regclass)
                    AND has_sequence_privilege('crm_clients_backup_reader',c.oid,'SELECT')))) THEN
  RAISE EXCEPTION 'UNSAFE_PUBLIC_SEQUENCE_PRIVILEGES';
 END IF;
 IF EXISTS(SELECT FROM pg_namespace WHERE nspname NOT LIKE 'pg_%'
           AND nspname<>'information_schema'
           AND has_schema_privilege('crm_clients_backup_reader',oid,'CREATE')) THEN
  RAISE EXCEPTION 'UNSAFE_PUBLIC_SCHEMA_CREATE';
 END IF;
 IF EXISTS(SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND p.prosecdef
           AND has_function_privilege('crm_clients_backup_reader',p.oid,'EXECUTE')) THEN
  RAISE EXCEPTION 'UNREVIEWED_EXECUTABLE_SECURITY_DEFINER';
 END IF;
END $audit$;
COMMIT;
