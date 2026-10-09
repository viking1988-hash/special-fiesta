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
[[ ! -e "$output" ]] || exit 1
partial="$output.partial"
trap 'rm -f "$partial"' EXIT
pg_dump --dbname="$DATABASE_URL" --format=custom --data-only --no-owner --no-acl --table=public.customers --table=public.vehicles | age -r "$AGE_RECIPIENT" -o "$partial"
[[ -s "$partial" ]] || exit 1
mv -- "$partial" "$output"
echo "CLIENT_BACKUP_ENCRYPTED_OK"
