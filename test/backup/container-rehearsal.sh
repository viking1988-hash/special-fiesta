#!/usr/bin/env bash
# Disposable container, network disabled, only artificial rows.
set -Eeuo pipefail
umask 077
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
bash scripts/crm-clients-export.sh /tmp/clients-20261009T000000Z.dump.age
python3 test/backup/roundtrip.py /tmp/clients-20261009T000000Z.dump.age /tmp/readback/clients-20261009T000000Z.dump.age
export CLIENT_BACKUP_ARCHIVE=/tmp/readback/clients-20261009T000000Z.dump.age
export AGE_IDENTITY_FILE=/tmp/identity TEST_DATABASE_URL=postgresql://postgres@127.0.0.1/crm_test_container_restore
export CLIENT_BACKUP_TEST_CONFIRM=ISOLATED CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED=YES CLIENT_BACKUP_EXPECTED_TEST_DB=crm_test_container_restore
bash scripts/crm-client-backup-verify.sh
test "$(psql -d crm_test_container_restore -Atqc 'SELECT count(*) FROM customers')" = 2
test "$(psql -d crm_test_container_restore -Atqc 'SELECT count(*) FROM vehicles v JOIN customers c ON c.id=v.customer_id AND c.organization_id=v.organization_id')" = 2
echo CONTAINER_SYNTHETIC_RECOVERY_OK
