"""Synthetic-only encrypted client export rehearsal.

No Railway credentials, production database URL, Yandex upload, or network access
is needed. Generates a synthetic CSV, encrypts it with an ephemeral age key,
and verifies decrypt/recovery entirely within a temporary local directory.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(argv, *, input_data=None):
    return subprocess.run(argv, input=input_data, capture_output=True, check=True, timeout=30)


def main():
    if os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES":
        raise SystemExit("SYNTHETIC_ONLY_REQUIRED")
    if os.environ.get("DATABASE_URL") or os.environ.get("YANDEX_DISK_TOKEN"):
        raise SystemExit("LIVE_CREDENTIALS_REFUSED")
    for command in ("age", "age-keygen"):
        if not shutil.which(command):
            raise SystemExit("AGE_TOOL_MISSING")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="client-synthetic-export-") as temp:
        directory = Path(temp)
        identity = directory / "identity.agekey"
        encrypted = directory / "clients-synthetic.age"
        run(["age-keygen", "-o", str(identity)])
        recipient = run(["age-keygen", "-y", str(identity)]).stdout.decode().strip()
        synthetic = b"organization_id,customer_id,vehicle_id\n1,101,201\n2,102,202\n"
        run(["age", "-r", recipient, "-o", str(encrypted)], input_data=synthetic)
        if not encrypted.read_bytes().startswith(b"age-encryption.org/v1\n"):
            raise SystemExit("ENCRYPTION_HEADER_INVALID")
        recovered = run(["age", "-d", "-i", str(identity), str(encrypted)]).stdout
        if recovered != synthetic:
            raise SystemExit("SYNTHETIC_RECOVERY_MISMATCH")
        if identity.stat().st_mode & 0o077:
            raise SystemExit("KEY_PERMISSIONS_UNSAFE")
        print("SYNTHETIC_CLIENT_EXPORT_ENCRYPTED_OK")
        print("SYNTHETIC_CLIENT_EXPORT_RECOVERY_OK")
        print("LIVE_DATABASE_CONNECTIONS=0 YANDEX_UPLOADS=0")


if __name__ == "__main__":
    main()
