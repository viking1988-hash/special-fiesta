#!/usr/bin/env bash
# Validate a client-only encrypted archive in an isolated test environment.
set -Eeuo pipefail
umask 077
: "${CLIENT_BACKUP_ARCHIVE:?Set path to encrypted archive}"
: "${AGE_IDENTITY_FILE:?Set path to private age identity}"
: "${TEST_DATABASE_URL:?Use an isolated disposable PostgreSQL database}"
[[ "${CLIENT_BACKUP_TEST_CONFIRM:-}" == "ISOLATED" ]] || { echo "Isolated database confirmation required" >&2; exit 1; }
for binary in age pg_restore psql; do command -v "$binary" >/dev/null || { echo "Missing tool: $binary" >&2; exit 1; }; done
[[ -s "$CLIENT_BACKUP_ARCHIVE" && -r "$AGE_IDENTITY_FILE" ]]
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
pg_restore --exit-on-error --single-transaction --data-only --no-owner --no-acl --dbname="$TEST_DATABASE_URL" "$workdir/clients.dump"
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -Atqc "
SELECT CASE WHEN EXISTS(
 SELECT 1 FROM public.vehicles v
 LEFT JOIN public.customers c ON c.id=v.customer_id
 WHERE v.customer_id IS NOT NULL AND c.id IS NULL
) THEN 'BROKEN_LINKS' ELSE 'LINKS_OK' END;"
echo "CLIENT_BACKUP_RESTORE_CHECK_FINISHED"
