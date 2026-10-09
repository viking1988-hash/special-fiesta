#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ "${CLIENT_BACKUP_ENABLED:-false}" == "true" ]] || { echo "CLIENT_BACKUP_DISABLED"; exit 0; }
: "${YANDEX_DISK_TOKEN:?}"
: "${1:?Provide encrypted archive path}"
archive="$1"
[[ -f "$archive" && -s "$archive" && "$archive" == *.dump.age ]] || { echo "Invalid encrypted archive path" >&2; exit 1; }
for tool in curl jq wc basename; do command -v "$tool" >/dev/null; done
name="$(basename -- "$archive")"
[[ "$name" =~ ^clients-[0-9]{8}T[0-9]{6}Z\.dump\.age$ ]] || { echo "Invalid backup filename" >&2; exit 1; }
remote="app:/clients-backups/$name"
api="https://cloud-api.yandex.net/v1/disk/resources"
auth="Authorization: OAuth $YANDEX_DISK_TOKEN"
# Create dedicated folder if absent; fail on unexpected errors.
status=$(curl -sS -o /dev/null -w '%{http_code}' -H "$auth" --get --data-urlencode 'path=app:/clients-backups' "$api")
if [[ "$status" == "404" ]]; then
  curl -fsS -X PUT -H "$auth" --get --data-urlencode 'path=app:/clients-backups' "$api" >/dev/null
elif [[ "$status" != "200" ]]; then
  echo "Yandex folder check failed" >&2; exit 1
fi
# Never overwrite a previous backup.
href=$(curl -fsS -H "$auth" --get --data-urlencode "path=$remote" --data-urlencode 'overwrite=false' "$api/upload" | jq -er '.href')
[[ "$href" == https://* ]] || { echo "Unexpected upload URL" >&2; exit 1; }
# Reject redirects so the OAuth token and encrypted archive cannot be sent to an unexpected host.
[[ "$href" != *"@"* ]] || { echo "Upload URL contains credentials" >&2; exit 1; }
# Yandex provides upload URLs on its storage hosts; reject unrelated destinations.
upload_host="${href#https://}"
upload_host="${upload_host%%/*}"
upload_host="${upload_host%%:*}"
[[ "$upload_host" == "uploader.disk.yandex.net" || "$upload_host" == *.disk.yandex.net || "$upload_host" == *.storage.yandex.net ]] || { echo "Untrusted Yandex upload host" >&2; exit 1; }
curl --proto "=https" --max-redirs 0 --connect-timeout 15 --max-time 900 -fsS -X PUT --upload-file "$archive" "$href" >/dev/null
local_bytes=$(wc -c < "$archive" | tr -d ' ')
remote_bytes=$(curl -fsS -H "$auth" --get --data-urlencode "path=$remote" "$api" | jq -er '.size')
[[ "$local_bytes" == "$remote_bytes" ]] || { echo "Yandex upload size mismatch" >&2; exit 1; }
echo "CLIENT_YANDEX_UPLOAD_OK bytes=$remote_bytes"
