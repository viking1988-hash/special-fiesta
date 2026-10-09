#!/usr/bin/env bash
# Validate a client-only encrypted archive in an isolated test environment.
set -Eeuo pipefail
umask 077
: "${CLIENT_BACKUP_ARCHIVE:?Set path to encrypted archive}"
: "${AGE_IDENTITY_FILE:?Set path to private age identity}"
: "${TEST_DATABASE_URL:?Use an isolated disposable PostgreSQL database}"
[[ "${CLIENT_BACKUP_TEST_CONFIRM:-}" == "ISOLATED" ]] || { echo "Isolated database confirmation required" >&2; exit 1; }
[[ "$TEST_DATABASE_URL" != *"production"* ]] || { echo "Production-looking database URL refused" >&2; exit 1; }
[[ "$TEST_DATABASE_URL" != *"crm-api"* ]] || { echo "Production-looking database URL refused" >&2; exit 1; }
[[ "${CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED:-}" == "YES" ]] || { echo "Confirm empty isolated test tables" >&2; exit 1; }
: "${CLIENT_BACKUP_EXPECTED_TEST_DB:?Set exact isolated database name}"
for binary in age pg_restore psql; do command -v "$binary" >/dev/null || { echo "Missing tool: $binary" >&2; exit 1; }; done
[[ -s "$CLIENT_BACKUP_ARCHIVE" && -r "$AGE_IDENTITY_FILE" ]]
actual_db=$(psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -Atqc "SELECT current_database()")
[[ "$actual_db" == "$CLIENT_BACKUP_EXPECTED_TEST_DB" ]] || { echo "Unexpected test database identity" >&2; exit 1; }
[[ "$actual_db" == crm_test_* || "$actual_db" == staging_* ]] || { echo "Test database name must be crm_test_* or staging_*" >&2; exit 1; }
# Database name alone is not proof of isolation. Refuse known production service hosts.
db_host=$(psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -Atqc "SELECT inet_server_addr()::text")
[[ -n "$db_host" ]] || { echo "Unable to confirm test server address" >&2; exit 1; }
[[ "$db_host" == "127.0.0.1" || "$db_host" == "::1" ]] || [[ "${CLIENT_BACKUP_REMOTE_TEST_APPROVED:-}" == "YES" ]] || { echo "Remote restore target requires explicit isolated-host approval" >&2; exit 1; }
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
age --decrypt -i "$AGE_IDENTITY_FILE" -o "$workdir/clients.dump" "$CLIENT_BACKUP_ARCHIVE"
[[ "$(head -c 5 "$workdir/clients.dump")" == "PGDMP" ]] || { echo "Invalid PostgreSQL archive" >&2; exit 1; }
pg_restore --list "$workdir/clients.dump" > "$workdir/contents.txt"
# Do not allow accidental restoration of any other data tables.
if grep -E ' TABLE DATA public ' "$workdir/contents.txt" | grep -Ev ' TABLE DATA public (customers|vehicles) ' >/dev/null; then
  echo "Unexpected table in client archive" >&2; exit 1
fi
for table in customers vehicles; do
  grep -Eq " TABLE DATA public $table " "$workdir/contents.txt" || { echo "Missing $table" >&2; exit 1; }
done
# The test database must have a reviewed schema installed already.
# Refuse a nonempty target: pg_restore --data-only can otherwise duplicate client data.
existing=$(psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -Atqc "SELECT (SELECT count(*) FROM public.customers) + (SELECT count(*) FROM public.vehicles)")
[[ "$existing" == "0" ]] || { echo "Test tables are not empty" >&2; exit 1; }
pg_restore --exit-on-error --single-transaction --data-only --no-owner --no-acl --dbname="$TEST_DATABASE_URL" "$workdir/clients.dump"
result=$(psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -Atqc "
SELECT CASE WHEN EXISTS(
 SELECT 1 FROM public.vehicles v
 LEFT JOIN public.customers c ON c.id=v.customer_id
 WHERE v.customer_id IS NOT NULL AND (c.id IS NULL OR c.organization_id IS DISTINCT FROM v.organization_id)
) THEN 'BROKEN_LINKS' ELSE 'LINKS_OK' END;")
[[ "$result" == "LINKS_OK" ]] || { echo "Client vehicle links invalid" >&2; exit 1; }
echo "CLIENT_BACKUP_RESTORE_OK"
