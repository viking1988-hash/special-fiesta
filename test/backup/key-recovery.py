"""Disposable artificial-key custody rehearsal; never a production identity.

Demonstrates restrictive storage, loss of the active copy, recovery from a second
copy, recipient equality and authenticated decryption. Both copies are destroyed.
It does not certify offline operator custody or protection against host loss.
"""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("KEY_RECOVERY_TOOL_FAILED")
    return result.stdout


def private(path, mode):
    metadata = path.stat()
    if path.is_symlink() or stat.S_IMODE(metadata.st_mode) != mode or metadata.st_uid != os.getuid():
        raise RuntimeError("KEY_STORAGE_PERMISSIONS_REFUSED")


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="artificial-key-recovery-") as directory:
        root = Path(directory)
        active, secondary, recovered = [root / name for name in ("active", "secondary", "recovered")]
        for path in (active, secondary, recovered):
            path.mkdir(mode=0o700)
            private(path, 0o700)
        identity = active / "identity.agekey"
        command(["age-keygen", "-o", str(identity)])
        private(identity, 0o600)
        recipient = command(["age-keygen", "-y", str(identity)]).decode().strip()
        ciphertext = root / "artificial.age"
        plaintext = b"ARTIFICIAL KEY RECOVERY ONLY\n"
        command(["age", "-r", recipient, "-o", str(ciphertext)], plaintext)
        backup = secondary / "identity.agekey"
        shutil.copyfile(identity, backup)
        backup.chmod(0o600)
        private(backup, 0o600)
        # Verify an over-broad identity is rejected, then restore safe permissions.
        backup.chmod(0o644)
        try:
            private(backup, 0o600)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("UNSAFE_KEY_STORAGE_ACCEPTED")
        backup.chmod(0o600)
        shutil.rmtree(active)
        if active.exists():
            raise RuntimeError("ACTIVE_KEY_NOT_REMOVED")
        restored = recovered / "identity.agekey"
        shutil.copyfile(backup, restored)
        restored.chmod(0o600)
        private(restored, 0o600)
        if command(["age-keygen", "-y", str(restored)]).decode().strip() != recipient:
            raise RuntimeError("RECOVERED_RECIPIENT_MISMATCH")
        if command(["age", "-d", "-i", str(restored), str(ciphertext)]) != plaintext:
            raise RuntimeError("RECOVERED_KEY_DECRYPT_MISMATCH")
        print("KEY_CUSTODY_REHEARSAL_OK active_copy_removed=YES directories=700 identities=600 unsafe_permissions_rejected=YES recovered_recipient_match=YES decrypt_match=YES", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("KEY_CUSTODY_REHEARSAL_FAILED")
