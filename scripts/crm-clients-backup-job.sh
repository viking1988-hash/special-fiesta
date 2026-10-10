#!/usr/bin/env bash
# Scheduled job: encrypted customer/vehicle export and Yandex upload.
set -Eeuo pipefail
umask 077
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workdir=""
on_exit() {
  local status=$?
  trap - EXIT
  if [[ -n "$workdir" ]]; then rm -rf -- "$workdir"; fi
  if [[ "$status" -ne 0 ]]; then
    echo "CLIENT_BACKUP_JOB_FAILED" >&2
    python3 "$here/../backup/notify.py" || true
  fi
  exit "$status"
}
trap on_exit EXIT
[[ "${CLIENT_BACKUP_ENABLED:-false}" == "true" ]] || { echo "CLIENT_BACKUP_DISABLED"; exit 0; }
[[ "${CLIENT_BACKUP_SCHEMA_VERIFIED:-}" == "YES" ]] || { echo "CLIENT_BACKUP_SCHEMA_UNVERIFIED" >&2; exit 1; }
[[ "${CLIENT_BACKUP_RESTORE_VERIFIED:-}" == "YES" ]] || { echo "CLIENT_BACKUP_RESTORE_UNVERIFIED" >&2; exit 1; }
[[ "${CLIENT_BACKUP_REQUIRE_ENCRYPTION:-true}" == "true" ]] || { echo "CLIENT_BACKUP_ENCRYPTION_REQUIRED" >&2; exit 1; }
: "${DATABASE_URL:?}"
: "${AGE_RECIPIENT:?}"
: "${YANDEX_DISK_TOKEN:?}"
workdir="$(mktemp -d)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$workdir/clients-$stamp.dump.age"
bash "$here/crm-clients-export.sh" "$archive"
[[ -s "$archive" ]] || { echo "CLIENT_BACKUP_EMPTY" >&2; exit 1; }
bash "$here/crm-clients-yandex-upload.sh" "$archive"
python3 "$here/../backup/yandex.py" retention-plan
echo "CLIENT_BACKUP_JOB_OK timestamp=$stamp"
# Retention deletion is intentionally not implemented until independently verified.
