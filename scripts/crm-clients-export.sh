#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ "${CLIENT_BACKUP_ENABLED:-false}" == "true" ]] || { echo "CLIENT_BACKUP_DISABLED"; exit 0; }
: "${DATABASE_URL:?}"
: "${AGE_RECIPIENT:?}"
: "${CLIENT_BACKUP_SCHEMA_VERIFIED:?}"
[[ "$CLIENT_BACKUP_SCHEMA_VERIFIED" == "YES" ]] || exit 1
command -v pg_dump >/dev/null
command -v age >/dev/null
output="${1:?Provide an encrypted output file path}"
[[ "$output" == *.age ]] || exit 1
[[ ! -e "$output" && ! -L "$output" ]] || exit 1
[[ "${CLIENT_BACKUP_REQUIRE_ENCRYPTION:-true}" == true ]] || exit 1
partial="$output.partial"
[[ ! -e "$partial" && ! -L "$partial" ]] || exit 1
trap 'rm -f "$partial"' EXIT
if ! PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=300000 -c lock_timeout=10000" pg_dump --dbname="$DATABASE_URL" --format=custom --data-only --no-owner --no-acl --table=public.customers --table=public.vehicles 2>/dev/null | age -r "$AGE_RECIPIENT" -o "$partial" 2>/dev/null; then
  echo "CLIENT_BACKUP_EXPORT_FAILED" >&2; exit 1
fi
[[ -s "$partial" ]] || exit 1
mv -- "$partial" "$output"
echo "CLIENT_BACKUP_ENCRYPTED_OK"
