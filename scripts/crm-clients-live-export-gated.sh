#!/usr/bin/env bash
# Mandatory live-only gate; never invoke the exporter in synthetic CI.
set -Eeuo pipefail
umask 077
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${CLIENT_BACKUP_LIVE_RUN_APPROVED:-}" != "YES" ]]; then
  echo "CLIENT_BACKUP_LIVE_APPROVAL_REQUIRED" >&2
  exit 1
fi
if [[ "${CLIENT_BACKUP_ENABLED:-false}" != "true" ]]; then
  echo "CLIENT_BACKUP_NOT_ENABLED" >&2
  exit 1
fi
if [[ "${SYNTHETIC_REHEARSAL_ONLY:-}" == "YES" ]]; then
  echo "CLIENT_BACKUP_SYNTHETIC_MODE_REFUSED" >&2
  exit 1
fi
# The preflight verifies configuration only; human-reviewed ACL, key custody,
# and independent recovery proof remain mandatory before deployment.
python3 -m backup.live_export_preflight
python3 -m backup.live_output_gate "$@"
# Reserve the final filename atomically. The legacy exporter refuses to
# overwrite an existing path, so use a separate private lock directory and
# reject concurrent invocation before any database access.
output="${1:?}"
lock="${output}.live-lock"
if ! mkdir -m 700 -- "$lock" 2>/dev/null; then
  echo "CLIENT_BACKUP_CONCURRENT_EXPORT_REFUSED" >&2
  exit 1
fi
cleanup() { rmdir -- "$lock" 2>/dev/null || true; }
trap cleanup EXIT
# Recheck after obtaining the lock, before pg_dump is invoked.
python3 -m backup.live_output_gate "$@"
bash "$here/crm-clients-export.sh" "$@"

