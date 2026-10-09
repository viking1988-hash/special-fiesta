#!/usr/bin/env bash
# Disposable container, only artificial rows. CI blocks external networking;
# Railway may opt into the authorized live Yandex test folder only.
set -Eeuo pipefail
umask 077
# Ignore all ambient database routing options: the source/target always live in this container.
unset PGDATABASE PGSERVICE PGSERVICEFILE PGHOSTADDR PGPORT PGPASSWORD DATABASE_URL TEST_DATABASE_URL
export SYNTHETIC_REHEARSAL_ONLY=YES
export PGDATA=/tmp/synthetic-pgdata PGHOST=127.0.0.1 PGUSER=postgres
initdb -D "$PGDATA" -A trust >/dev/null
pg_ctl -D "$PGDATA" -o '-c listen_addresses=127.0.0.1' -w start >/dev/null
trap 'pg_ctl -D "$PGDATA" -m immediate stop >/dev/null 2>&1 || true; rm -rf /tmp/identity /tmp/clients-*.dump.age /tmp/readback' EXIT
psql -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE crm_test_container_source' >/dev/null
psql -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE crm_test_container_restore' >/dev/null
for db in crm_test_container_source crm_test_container_restore; do
  psql -d "$db" -v ON_ERROR_STOP=1 -c 'CREATE TABLE customers(id bigint PRIMARY KEY, organization_id bigint, name text); CREATE TABLE vehicles(id bigint PRIMARY KEY, organization_id bigint, customer_id bigint REFERENCES customers(id));' >/dev/null
done
psql -d crm_test_container_source -v ON_ERROR_STOP=1 -c 'INSERT INTO customers VALUES(1,1,$$ARTIFICIAL ONLY$$),(2,2,NULL); INSERT INTO vehicles VALUES(1,1,1),(2,2,2);' >/dev/null
age-keygen -o /tmp/identity 2>/dev/null
export AGE_RECIPIENT
AGE_RECIPIENT="$(age-keygen -y /tmp/identity)"
export CLIENT_BACKUP_ENABLED=true CLIENT_BACKUP_SCHEMA_VERIFIED=YES
export DATABASE_URL=postgresql://postgres@127.0.0.1/crm_test_container_source
archive="/tmp/clients-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
readback="/tmp/readback/$(basename -- "$archive")"
bash scripts/crm-clients-export.sh "$archive"
if [[ "${CLIENT_BACKUP_LIVE_YANDEX_TEST:-false}" == true ]]; then
  python3 test/backup/live-roundtrip.py "$archive" "$readback"
else
  python3 test/backup/roundtrip.py "$archive" "$readback"
fi
export CLIENT_BACKUP_ARCHIVE="$readback"
export AGE_IDENTITY_FILE=/tmp/identity TEST_DATABASE_URL=postgresql://postgres@127.0.0.1/crm_test_container_restore
export CLIENT_BACKUP_TEST_CONFIRM=ISOLATED CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED=YES CLIENT_BACKUP_EXPECTED_TEST_DB=crm_test_container_restore
bash scripts/crm-client-backup-verify.sh
test "$(psql -d crm_test_container_restore -Atqc 'SELECT count(*) FROM customers')" = 2
test "$(psql -d crm_test_container_restore -Atqc 'SELECT count(*) FROM vehicles v JOIN customers c ON c.id=v.customer_id AND c.organization_id=v.organization_id')" = 2
for table in customers vehicles; do
  source_hash=$(psql -d crm_test_container_source -Atqc "SELECT md5(coalesce(string_agg(row_to_json(t)::text, '|' ORDER BY id), '')) FROM $table t")
  restore_hash=$(psql -d crm_test_container_restore -Atqc "SELECT md5(coalesce(string_agg(row_to_json(t)::text, '|' ORDER BY id), '')) FROM $table t")
  test "$source_hash" = "$restore_hash"
done
psql -d crm_test_container_restore -X -v ON_ERROR_STOP=1 -f scripts/crm-client-schema-audit.sql >/dev/null
echo CONTAINER_SYNTHETIC_METADATA_AUDIT_OK
echo CONTAINER_SYNTHETIC_RECOVERY_OK

echo SYNTHETIC_REHEARSAL_DONE customers=2 vehicles=2 links=2
