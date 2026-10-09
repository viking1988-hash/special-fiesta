#!/usr/bin/env bash
# Run on the operator's trusted offline machine, NEVER in Railway or CI.
set -Eeuo pipefail
umask 077
[[ "${CLIENT_BACKUP_OFFLINE_KEY_SETUP:-}" == YES ]] || { echo "OFFLINE_KEY_SETUP_REQUIRED" >&2; exit 1; }
key_dir="${1:?Provide a NEW private key directory on a trusted machine}"
[[ ! -e "$key_dir" && ! -L "$key_dir" ]] || { echo "EXISTING_KEY_DIRECTORY_REFUSED" >&2; exit 1; }
command -v age-keygen >/dev/null
mkdir -m 700 -- "$key_dir"
age-keygen -o "$key_dir/identity.agekey" 2>/dev/null
age-keygen -y "$key_dir/identity.agekey" > "$key_dir/recipient.txt"
chmod 600 "$key_dir/identity.agekey" "$key_dir/recipient.txt"
echo "KEY_FILES_CREATED: keep identity offline; only recipient.txt goes to Railway"
