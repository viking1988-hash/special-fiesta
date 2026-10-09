"""Read an existing snapshot; restore SCHEMA ONLY, never customer rows.

One-shot, loopback-only database. Logs contain metadata and artificial-test counters.
No production DATABASE_URL, network database connection, upload or S3 mutation.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def run(args, *, sql=None):
    result = subprocess.run(args, input=sql, capture_output=True, text=True, timeout=300)
    if result.returncode:
        # Database errors can contain row values; never expose raw stderr.
        raise RuntimeError("REHEARSAL_COMMAND_FAILED tool=" + Path(args[0]).name)
    return result.stdout


def query(db, sql):
    return run(["psql", "-X", "-d", db, "-v", "ON_ERROR_STOP=1", "-Atqc", sql]).strip()


def main():
    if os.environ.get("CLIENT_BACKUP_SCHEMA_REHEARSAL") != "true" or os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES":
        print("SCHEMA_REHEARSAL_DISABLED", flush=True)
        return
    os.umask(0o077)
    for key in ("DATABASE_URL", "TEST_DATABASE_URL", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGPORT", "PGPASSWORD"):
        os.environ.pop(key, None)
    if os.environ.get("CLIENT_BACKUP_LIVE_ALERT_TEST") == "true":
        print(run(["python3", "test/backup/live-alert.py"]).strip(), flush=True)
    work = Path(tempfile.mkdtemp(prefix="schema-rehearsal-"))
    os.environ.update(PGDATA=str(work / "pgdata"), PGHOST="127.0.0.1", PGUSER="postgres")
    started = False
    try:
        run(["initdb", "-D", os.environ["PGDATA"], "-A", "trust"])
        run(["pg_ctl", "-D", os.environ["PGDATA"], "-l", str(work / "pg.log"), "-o", "-c listen_addresses=127.0.0.1", "-w", "start"])
        started = True
        bucket = os.environ["BACKUP_BUCKET"]
        endpoint = os.environ["BACKUP_ENDPOINT"]
        # endpoint comes from the existing restore service, not caller-supplied URLs.
        if not endpoint.startswith("https://"):
            raise RuntimeError("SNAPSHOT_ENDPOINT_TLS_REQUIRED")
        objects = json.loads(run(["aws", "s3api", "list-objects-v2", "--bucket", bucket,
                                  "--prefix", "crm-", "--endpoint-url", endpoint, "--output", "json"]))
        archives = [x for x in objects.get("Contents", []) if re.fullmatch(r"crm-\d{8}-\d{6}\.dump", x["Key"])]
        latest = max(archives, key=lambda x: x["LastModified"])
        if not 1024 <= latest["Size"] <= 500 * 1024 * 1024:
            raise RuntimeError("SNAPSHOT_SIZE_REFUSED")
        archive = work / "snapshot.dump"
        run(["aws", "s3api", "get-object", "--bucket", bucket, "--key", latest["Key"],
             "--endpoint-url", endpoint, str(archive)])
        with archive.open("rb") as stream:
            if archive.stat().st_size != latest["Size"] or stream.read(5) != b"PGDMP":
                raise RuntimeError("SNAPSHOT_ARCHIVE_INVALID")
            stream.seek(0)
            snapshot_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        print("SNAPSHOT_SCHEMA_SOURCE key=" + latest["Key"] + " modified=" + latest["LastModified"] + " sha256=" + snapshot_hash, flush=True)
        source = "crm_test_real_schema_source"
        target = "crm_test_real_schema_restore"
        for db in (source, target):
            run(["createdb", db])
            run(["pg_restore", "--schema-only", "--exit-on-error", "--no-owner", "--no-acl", "--dbname=" + db, str(archive)])
            if query(db, "SELECT (SELECT count(*) FROM public.customers)+(SELECT count(*) FROM public.vehicles)") != "0":
                raise RuntimeError("SCHEMA_ONLY_TARGET_NOT_EMPTY")
        archive.unlink()
        print("SCHEMA_ONLY_RESTORE_OK databases=2 customer_rows=0 vehicle_rows=0 snapshot_removed=YES", flush=True)
        print("REAL_SCHEMA_METADATA_BEGIN", flush=True)
        print(run(["psql", "-X", "-d", source, "-v", "ON_ERROR_STOP=1", "-f", "scripts/crm-client-schema-audit.sql"]), flush=True)
        # Organization metadata only, to review required prerequisite columns.
        print(query(source, "SELECT column_name||'|'||data_type||'|'||is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='organizations' ORDER BY ordinal_position"), flush=True)
        print("REAL_SCHEMA_METADATA_END", flush=True)
        print("REAL_SCHEMA_AUDIT_OK", flush=True)
    finally:
        if started:
            subprocess.run(["pg_ctl", "-D", os.environ["PGDATA"], "-m", "immediate", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(work)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Only our own fixed errors are printable, never provider/SQL text.
        print(str(exc) if isinstance(exc, RuntimeError) else "SCHEMA_REHEARSAL_FAILED", flush=True)
        raise SystemExit(1)
