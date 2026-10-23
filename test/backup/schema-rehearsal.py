"""Read an existing snapshot; restore SCHEMA ONLY, never customer rows.

One-shot, loopback-only database. Logs contain metadata and artificial-test counters.
No production DATABASE_URL, network database connection, upload or S3 mutation.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import runpy
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
    if os.environ.get("CLIENT_BACKUP_SCHEMA_ONLY_SOURCE_REVIEWED") != "YES":
        raise RuntimeError("SCHEMA_ONLY_SOURCE_REVIEW_REQUIRED")
    os.umask(0o077)
    for key in ("DATABASE_URL", "TEST_DATABASE_URL", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGPORT", "PGPASSWORD", "PGOPTIONS"):
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
        # Fail closed on malformed reviewed-source selectors before storage access.
        import importlib.util
        validator_path = Path(__file__).with_name("schema_source_preflight.py")
        validator_spec = importlib.util.spec_from_file_location("schema_source_preflight", validator_path)
        validator = importlib.util.module_from_spec(validator_spec)
        validator_spec.loader.exec_module(validator)
        validator.validate_schema_source(
            os.environ.get("CLIENT_BACKUP_SCHEMA_ONLY_OBJECT_KEY", ""),
            os.environ.get("CLIENT_BACKUP_SCHEMA_ONLY_SHA256", ""),
        )
        bucket = os.environ["BACKUP_BUCKET"]
        endpoint = os.environ["BACKUP_ENDPOINT"]
        # endpoint comes from the existing restore service, not caller-supplied URLs.
        if not endpoint.startswith("https://"):
            raise RuntimeError("SNAPSHOT_ENDPOINT_TLS_REQUIRED")
        reviewed_key = os.environ.get("CLIENT_BACKUP_SCHEMA_ONLY_OBJECT_KEY", "")
        if not re.fullmatch(r"crm-schema-only-\d{8}-\d{6}\.dump", reviewed_key):
            raise RuntimeError("SCHEMA_ONLY_OBJECT_KEY_REQUIRED")
        objects = json.loads(run(["aws", "s3api", "list-objects-v2", "--bucket", bucket,
                                  "--prefix", reviewed_key, "--endpoint-url", endpoint, "--output", "json"]))
        archives = [x for x in objects.get("Contents", []) if x["Key"] == reviewed_key]
        if len(archives) != 1:
            raise RuntimeError("SNAPSHOT_ARCHIVE_NOT_FOUND")
        latest = archives[0]
        if not 1024 <= latest["Size"] <= 500 * 1024 * 1024:
            raise RuntimeError("SNAPSHOT_SIZE_REFUSED")
        expected_hash = os.environ.get("CLIENT_BACKUP_SCHEMA_ONLY_SHA256", "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise RuntimeError("SCHEMA_ONLY_EXPECTED_SHA256_REQUIRED")
        archive = work / "snapshot.dump"
        run(["aws", "s3api", "get-object", "--bucket", bucket, "--key", latest["Key"],
             "--endpoint-url", endpoint, str(archive)])
        with archive.open("rb") as stream:
            if archive.stat().st_size != latest["Size"] or stream.read(5) != b"PGDMP":
                raise RuntimeError("SNAPSHOT_ARCHIVE_INVALID")
            stream.seek(0)
            snapshot_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if snapshot_hash != expected_hash:
            raise RuntimeError("SCHEMA_ONLY_SHA256_MISMATCH")
        # A reviewed source flag is not proof of content: refuse data-bearing archives.
        toc = run(["pg_restore", "--list", str(archive)])
        if any(re.search(r"\b(TABLE DATA|BLOBS|BLOB|LARGE OBJECT|MATERIALIZED VIEW DATA)\b", line)
               for line in toc.splitlines() if line and not line.startswith(";")):
            raise RuntimeError("SNAPSHOT_CONTAINS_DATA_REFUSED")
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
        print(run(["python3", "test/backup/key-recovery.py"]).strip(), flush=True)
        for db in (source, target):
            query(db, "INSERT INTO organizations(id,name,timezone,created_at) VALUES (1,'ARTIFICIAL ORG ONE','Europe/Moscow','2026-01-01'),(2,'ARTIFICIAL ORG TWO','Europe/Moscow','2026-01-01')")
        query(source, """
INSERT INTO customers(organization_id,name,phone,email,created_at,consent_personal_data_at)
VALUES (1,'ARTIFICIAL ONE','+70000000001','one@example.invalid','2026-01-01','2026-01-01'),
       (2,'ARTIFICIAL TWO','+70000000001',NULL,'2026-01-01',NULL);
INSERT INTO vehicles(organization_id,customer_id,make,model,year,plate,vin,created_at,mileage)
VALUES (1,1,'ARTIFICIAL','ONE',2020,'TEST-ONE','TEST0000000000001','2026-01-01',0),
       (2,2,'ARTIFICIAL','TWO',NULL,NULL,NULL,'2026-01-01',NULL),
       (1,NULL,'ARTIFICIAL','UNASSIGNED',2021,NULL,NULL,'2026-01-01',100);
""")
        # Tenant phone uniqueness, source FKs and mileage CHECK are real constraints.
        query(source, """
DO $test$ BEGIN
 BEGIN INSERT INTO customers(organization_id,name,phone) VALUES(1,'ARTIFICIAL DUPLICATE','+70000000001'); RAISE EXCEPTION 'uniqueness failed'; EXCEPTION WHEN unique_violation THEN NULL; END;
 BEGIN INSERT INTO vehicles(organization_id,customer_id,make,model) VALUES(1,9999,'ARTIFICIAL','BAD LINK'); RAISE EXCEPTION 'FK failed'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
 BEGIN INSERT INTO vehicles(organization_id,make,model,mileage) VALUES(1,'ARTIFICIAL','BAD MILEAGE',-1); RAISE EXCEPTION 'CHECK failed'; EXCEPTION WHEN check_violation THEN NULL; END;
END $test$;
""")
        print("REAL_SCHEMA_SOURCE_CONSTRAINTS_OK unique_phone=YES customer_fk=YES mileage_check=YES", flush=True)
        run(["psql", "-X", "-d", source, "-v", "ON_ERROR_STOP=1",
             "-v", "expected_database=" + source, "-v", "reader_role_install=REVIEWED_ROLE_ONLY",
             "-f", "scripts/crm-client-reader-role.sql"])
        runpy.run_path('test/backup/reader-permissions.py')['test_permissions'](source)
        print('READER_ROLE_CREATED scope=ISOLATED_ONLY login_password=UNSET', flush=True)
        active = work / "active"
        secondary = work / "secondary"
        recovered = work / "recovered"
        for directory in (active, secondary, recovered):
            directory.mkdir(mode=0o700)
        identity = active / "identity.agekey"
        run(["age-keygen", "-o", str(identity)])
        recipient = run(["age-keygen", "-y", str(identity)]).strip()
        recovery_identity = secondary / "recovery-identity.agekey"
        run(["age-keygen", "-o", str(recovery_identity)])
        recovery_recipient = run(["age-keygen", "-y", str(recovery_identity)]).strip()
        if recipient == recovery_recipient:
            raise RuntimeError("REHEARSAL_RECIPIENTS_NOT_DISTINCT")
        os.environ.update(CLIENT_BACKUP_ENABLED="true", CLIENT_BACKUP_SCHEMA_VERIFIED="YES",
                          AGE_RECIPIENT_PRIMARY=recipient, AGE_RECIPIENT_RECOVERY=recovery_recipient,
                          DATABASE_URL="postgresql://crm_clients_backup_reader@127.0.0.1/" + source)
        encrypted = work / "clients-artificial.dump.age"
        print(run(["bash", "scripts/crm-clients-export.sh", str(encrypted)]).strip(), flush=True)
        # Prove the independent recovery identity decrypts this same archive.
        # Discard plaintext; do not print or persist customer data.
        run(["age", "--decrypt", "-i", str(recovery_identity), "-o", os.devnull, str(encrypted)])
        print("READER_ROLE_DUAL_RECIPIENT_DECRYPT_OK", flush=True)
        print('READER_ROLE_ENCRYPTED_EXPORT_OK', flush=True)
        backup_key = secondary / "identity.agekey"
        shutil.copyfile(identity, backup_key)
        backup_key.chmod(0o600)
        shutil.rmtree(active)
        recovered_key = recovered / "identity.agekey"
        shutil.copyfile(backup_key, recovered_key)
        recovered_key.chmod(0o600)
        if stat.S_IMODE(recovered_key.stat().st_mode) != 0o600 or run(["age-keygen", "-y", str(recovered_key)]).strip() != recipient:
            raise RuntimeError("RECOVERED_ARCHIVE_KEY_INVALID")
        os.environ.update(CLIENT_BACKUP_ARCHIVE=str(encrypted), AGE_IDENTITY_FILE=str(recovered_key),
                          TEST_DATABASE_URL="postgresql://postgres@127.0.0.1/" + target,
                          CLIENT_BACKUP_TEST_CONFIRM="ISOLATED", CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED="YES",
                          CLIENT_BACKUP_EXPECTED_TEST_DB=target,
                          CLIENT_BACKUP_EXPECTED_CLUSTER_ID=query("postgres", "SELECT system_identifier FROM pg_control_system()"))
        print(run(["bash", "scripts/crm-client-backup-verify.sh"]).strip(), flush=True)
        for table in ("customers", "vehicles"):
            sql = "SELECT md5(coalesce(string_agg(row_to_json(t)::text, '|' ORDER BY id), '')) FROM " + table + " t"
            if query(source, sql) != query(target, sql):
                raise RuntimeError("REAL_SCHEMA_ROW_DIGEST_MISMATCH")
        if query(target, "SELECT (SELECT count(*) FROM customers)||'|'||(SELECT count(*) FROM vehicles)||'|'||(SELECT count(*) FROM vehicles v JOIN customers c ON c.id=v.customer_id AND c.organization_id=v.organization_id)||'|'||(SELECT count(*) FROM vehicles WHERE customer_id IS NULL)") != "2|3|2|1":
            raise RuntimeError("REAL_SCHEMA_COUNTS_MISMATCH")
        print("REAL_SCHEMA_RECOVERY_OK customers=2 vehicles=3 tenant_links=2 nullable_owner=1 full_row_digests=MATCH recovered_key=YES", flush=True)
        # Test real post-recovery writes; sequence gaps from rejected source inserts
        # must also survive backup, so MAX(id) alone is not sufficient evidence.
        for table in ("customers", "vehicles"):
            sequence = query(source, "SELECT pg_get_serial_sequence('public." + table + "','id')")
            if sequence not in ("public.customers_id_seq", "public.vehicles_id_seq"):
                raise RuntimeError("REAL_SCHEMA_SEQUENCE_UNREVIEWED")
            if query(source, "SELECT last_value||'|'||is_called FROM " + sequence) != query(target, "SELECT last_value||'|'||is_called FROM " + sequence):
                raise RuntimeError("REAL_SCHEMA_SEQUENCE_STATE_MISMATCH table=" + table)
        next_customer = query(target, "INSERT INTO customers(organization_id,name,phone) VALUES(1,'ARTIFICIAL AFTER RESTORE','+70000000002') RETURNING id")
        next_vehicle = query(target, "INSERT INTO vehicles(organization_id,customer_id,make,model) VALUES(1," + next_customer.splitlines()[0] + ",'ARTIFICIAL','AFTER RESTORE') RETURNING id")
        if int(next_customer.splitlines()[0]) <= 2 or int(next_vehicle.splitlines()[0]) <= 3:
            raise RuntimeError("REAL_SCHEMA_SEQUENCE_WRITE_FAILED")
        print("REAL_SCHEMA_SEQUENCE_RECOVERY_OK customer_insert=YES vehicle_insert=YES", flush=True)
        print("REAL_SCHEMA_REHEARSAL_DONE", flush=True)
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
