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
[[ ! -L "$archive" ]] || { echo "Symlink archive refused" >&2; exit 1; }
[[ "${CLIENT_BACKUP_REQUIRE_ENCRYPTION:-true}" == "true" ]] || { echo "Encryption must remain required" >&2; exit 1; }
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null
python3 "$here/../backup/yandex.py" upload "$archive"
