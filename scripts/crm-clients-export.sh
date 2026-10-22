#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ "${CLIENT_BACKUP_ENABLED:-false}" == "true" ]] || { echo "CLIENT_BACKUP_DISABLED"; exit 0; }
: "${DATABASE_URL:?}"
: "${AGE_RECIPIENT_PRIMARY:?}"
: "${AGE_RECIPIENT_RECOVERY:?}"
recipient_pattern='^age1[023456789acdefghjklmnpqrstuvwxyz]{58}
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
cleanup_partial() {
  if [[ -f "$partial" && ! -L "$partial" ]]; then
    rm -f -- "$partial"
  fi
}
trap cleanup_partial EXIT
if ! PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=300000 -c lock_timeout=10000" pg_dump --dbname="$DATABASE_URL" --format=custom --data-only --no-owner --no-acl --table=public.customers --table=public.vehicles 2>/dev/null | age -r "$AGE_RECIPIENT_PRIMARY" -r "$AGE_RECIPIENT_RECOVERY" -o "$partial" 2>/dev/null; then
  echo "CLIENT_BACKUP_EXPORT_FAILED" >&2; exit 1
fi
[[ -s "$partial" ]] || exit 1
# Refuse malformed output even when an encryption command exits successfully.
[[ "$(head -c 22 -- "$partial")" == "age-encryption.org/v1" ]] || {
  echo "CLIENT_BACKUP_INVALID_ENCRYPTED_HEADER" >&2
  exit 1
}
# Atomic no-clobber publication: hard-link creation fails if output already exists.
# Both names are in the same private directory/filesystem.
[[ -f "$partial" && ! -L "$partial" ]] || exit 1
if ! ln -- "$partial" "$output"; then
  echo "CLIENT_BACKUP_OUTPUT_ALREADY_EXISTS" >&2
  exit 1
fi
rm -- "$partial"
echo "CLIENT_BACKUP_ENCRYPTED_OK"

[[ "$AGE_RECIPIENT_PRIMARY" =~ $recipient_pattern ]] || { echo "CLIENT_BACKUP_PRIMARY_RECIPIENT_INVALID" >&2; exit 1; }
[[ "$AGE_RECIPIENT_RECOVERY" =~ $recipient_pattern ]] || { echo "CLIENT_BACKUP_RECOVERY_RECIPIENT_INVALID" >&2; exit 1; }
[[ "$AGE_RECIPIENT_PRIMARY" != "$AGE_RECIPIENT_RECOVERY" ]] || { echo "CLIENT_BACKUP_RECIPIENTS_NOT_DISTINCT" >&2; exit 1; }
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
cleanup_partial() {
  if [[ -f "$partial" && ! -L "$partial" ]]; then
    rm -f -- "$partial"
  fi
}
trap cleanup_partial EXIT
if ! PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=300000 -c lock_timeout=10000" pg_dump --dbname="$DATABASE_URL" --format=custom --data-only --no-owner --no-acl --table=public.customers --table=public.vehicles 2>/dev/null | age -r "$AGE_RECIPIENT" -o "$partial" 2>/dev/null; then
  echo "CLIENT_BACKUP_EXPORT_FAILED" >&2; exit 1
fi
[[ -s "$partial" ]] || exit 1
# Refuse malformed output even when an encryption command exits successfully.
[[ "$(head -c 22 -- "$partial")" == "age-encryption.org/v1" ]] || {
  echo "CLIENT_BACKUP_INVALID_ENCRYPTED_HEADER" >&2
  exit 1
}
# Atomic no-clobber publication: hard-link creation fails if output already exists.
# Both names are in the same private directory/filesystem.
[[ -f "$partial" && ! -L "$partial" ]] || exit 1
if ! ln -- "$partial" "$output"; then
  echo "CLIENT_BACKUP_OUTPUT_ALREADY_EXISTS" >&2
  exit 1
fi
rm -- "$partial"
echo "CLIENT_BACKUP_ENCRYPTED_OK"
