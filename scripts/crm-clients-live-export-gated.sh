#!/usr/bin/env bash
# Mandatory live-only gate; never invoke the exporter in synthetic CI.
set -Eeuo pipefail
umask 077
if [[ "${CLIENT_BACKUP_LIVE_RUN_APPROVED:-}" != "YES" ]]; then
  echo "CLIENT_BACKUP_LIVE_APPROVAL_REQUIRED" >&2
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
exec bash scripts/crm-clients-export.sh "$@"
