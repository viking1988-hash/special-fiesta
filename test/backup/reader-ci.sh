#!/usr/bin/env bash
# Actual ACL and pg_dump test, disconnected container and artificial schema only.
set -Eeuo pipefail
umask 077
unset DATABASE_URL TEST_DATABASE_URL PGDATABASE PGSERVICE PGSERVICEFILE PGHOSTADDR PGPORT PGPASSWORD PGOPTIONS
work="$(mktemp -d)"
export PGDATA="$work/pgdata" PGHOST=127.0.0.1 PGUSER=postgres
trap 'pg_ctl -D "$PGDATA" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$work"' EXIT
initdb -D "$PGDATA" -A trust >/dev/null
pg_ctl -D "$PGDATA" -l "$work/pg.log" -o '-c listen_addresses=127.0.0.1' -w start >/dev/null
createdb crm_test_reader_ci
psql -X -d crm_test_reader_ci -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
CREATE TABLE organizations(id bigint PRIMARY KEY);
CREATE TABLE customers(id bigserial PRIMARY KEY,organization_id bigint,name text,phone text);
CREATE TABLE vehicles(id bigserial PRIMARY KEY,organization_id bigint,customer_id bigint,make text,model text);
CREATE TABLE bookings(id bigint); CREATE TABLE work_orders(id bigint); CREATE TABLE customer_contact_events(id bigint);
INSERT INTO customers(organization_id,name,phone) VALUES(1,'ARTIFICIAL','+70000000001'),(2,'ARTIFICIAL','+70000000002');
INSERT INTO vehicles(organization_id,customer_id,make,model) VALUES(1,1,'ARTIFICIAL','ONE'),(2,2,'ARTIFICIAL','TWO'),(1,NULL,'ARTIFICIAL','THREE');
SQL
# Reject installation even when the supplied expected_database matches a non-test DB.
createdb crm_reader_ci_unsafe
if psql -X -d crm_reader_ci_unsafe -v ON_ERROR_STOP=1 \
  -v expected_database=crm_reader_ci_unsafe -v reader_role_install=REVIEWED_ROLE_ONLY \
  -f scripts/crm-client-reader-role.sql >"$work/non-test-guard.log" 2>&1; then
  echo NON_TEST_DATABASE_GUARD_FAILED >&2
  exit 1
fi
if ! grep -q 'ROLE_INSTALL_TARGET_UNCONFIRMED' "$work/non-test-guard.log"; then
  echo NON_TEST_DATABASE_GUARD_WRONG_FAILURE >&2
  exit 1
fi
if psql -X -d crm_reader_ci_unsafe -Atqc "SELECT 1 FROM pg_roles WHERE rolname='crm_clients_backup_reader'" | grep -q 1; then
  echo NON_TEST_DATABASE_ROLE_CREATED >&2
  exit 1
fi
echo NON_TEST_DATABASE_GUARD_OK
psql -X -d crm_test_reader_ci -v ON_ERROR_STOP=1 -v expected_database=crm_test_reader_ci -v reader_role_install=REVIEWED_ROLE_ONLY -f scripts/crm-client-reader-role.sql >/dev/null
python3 test/backup/reader-permissions.py crm_test_reader_ci
age-keygen -o "$work/identity" 2>/dev/null
age-keygen -o "$work/recovery-identity" 2>/dev/null
AGE_RECIPIENT_PRIMARY="$(age-keygen -y "$work/identity")"
AGE_RECIPIENT_RECOVERY="$(age-keygen -y "$work/recovery-identity")"
export CLIENT_BACKUP_ENABLED=true CLIENT_BACKUP_SCHEMA_VERIFIED=YES
test "$AGE_RECIPIENT_PRIMARY" != "$AGE_RECIPIENT_RECOVERY"
export AGE_RECIPIENT_PRIMARY AGE_RECIPIENT_RECOVERY
export DATABASE_URL=postgresql://crm_clients_backup_reader@127.0.0.1/crm_test_reader_ci
bash scripts/crm-clients-export.sh "$work/reader.dump.age"
age -d -i "$work/recovery-identity" "$work/reader.dump.age" | pg_restore -l >/dev/null
echo READER_CI_ENCRYPTED_EXPORT_OK
