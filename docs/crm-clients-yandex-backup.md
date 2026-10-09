# CRM client-only Yandex Disk backup — rollout checklist

Status: **not enabled**. Railway service `crm-clients-yandex-backup` is staged only; it must not be applied until encryption and restore tests pass.

## Verified data model
The isolated `crm-restore-test` command (read-only inspection, 2026-10-09) references `customers` and `vehicles` tables. `vehicles.customer_id` points to `customers.id`; both include `organization_id`. This is evidence of table names and basic relationships, **not** a complete column/constraint inventory.

## Required implementation
1. On a restored **isolated** snapshot, inspect `information_schema.columns`, foreign keys and dependencies for `public.customers` and `public.vehicles`; do not guess schema or export extra tables.
2. Export only these tables with PostgreSQL `pg_dump --format=custom --data-only --table=public.customers --table=public.vehicles`, plus separately versioned, reviewed schema/restore instructions. Preserve ownership relationships and test import into an isolated database with matching schema.
3. Encrypt the archive **before upload** with authenticated encryption (e.g. age recipient-based encryption); store decryption private key outside Railway and Yandex Disk. Fail closed when key is absent.
4. Upload to a dedicated non-public app folder `app:/clients-backups/`, using a unique timestamped `.dump.age` name; verify remote size and digest where supported. Do not log client data, credentials or presigned URLs.
5. Run restore tests in a disposable PostgreSQL database. Verify customer and vehicle counts, referential integrity and representative joins, without printing PII.
6. Only after successful restore and retention-policy review, enable daily schedule and retention of the most recent 30 days; do not delete any old backup before the new backup is verified.
7. Record operator approval, runbook, failure alerts, and tested decryption-key recovery procedure.

## Railway safeguards
- Production project `Avtohirurg-CRM`; separate service `crm-clients-yandex-backup` currently has `CLIENT_BACKUP_ENABLED=false` and `CLIENT_BACKUP_REQUIRE_ENCRYPTION=true` in a staged patch.
- The service currently has a deliberate failing start command; it does **not** export or upload customer records.
- Do not copy the production `DATABASE_URL` or Yandex OAuth token into the staging project.
- Existing full CRM backup and `crm-yandex-mirror` must remain unchanged.

## Implementation blocker verified 2026-10-09
The staged Railway service has no database connection, Yandex token, or encryption recipient configured. It is intentionally set to fail and must **not** be activated. Before writing the export job, verify exact table dependencies in a restored snapshot. A streaming pipeline must propagate `pg_dump` failure (e.g. Bash `set -o pipefail`); successful encryption alone must never count as a successful dump. Use a distinct Yandex path and do not automatically delete historical copies until retention has been tested. A source upload attempt was blocked; no export script has been deployed.

## CI verification — 2026-10-09
- `CRM client backup checks` succeeded for commit `57b3cb1e` (run `37966169060`), including syntax, disabled defaults, and missing safety gate rejection.
- CRM auth and Jarvis PR checks succeeded at the same commit. PostgreSQL integration checks were still running when inspected.
- **CI success does not establish an actual encrypted export, Yandex upload, or recovery rehearsal.** Keep the Railway client-only backup service staged and disabled until a restore has been demonstrated.

## Deployment blocker: shell executable permissions (verified 2026-10-09)
GitHub tree inspection confirms all four client-backup shell scripts have mode `100644`, not executable `100755`. The orchestrator currently calls `crm-clients-export.sh` and `crm-clients-yandex-upload.sh` directly; that will fail with `Permission denied` in a deployment that preserves these modes. The attempted orchestrator edit was blocked, and **no fix was committed**. Before enabling the job, explicitly verify executable modes or make the orchestrator invoke each child with Bash, then exercise the end-to-end job in an isolated environment. Existing CI syntax and disabled-state checks do not cover this execution path.

## Resolved shell execution blocker — 2026-10-09
- Commit `c11df870` changed the orchestrator to call both child scripts with `bash`, so GitHub's `100644` file mode no longer prevents execution of these child steps.
- Commit `c4e066bf` added a regression assertion to CI. `CRM client backup checks` succeeded for `c4e066bf` (run `37966559285`).
- This closes the shell execution issue only; a real age-encrypted PostgreSQL export, Yandex upload, and isolated restore remain untested. Do not enable the dedicated service yet.

## CI static-analysis and encryption-gate status — 2026-10-09
- ShellCheck passed in `CRM client backup checks` on commit `fff86671` (run `37966836103`).
- The explicit test rejecting `CLIENT_BACKUP_REQUIRE_ENCRYPTION=false` passed on commit `9e1fd2e4` (run `37966921056`).
- These are static and negative-path checks, **not** evidence of successful encryption, upload, or recovery. A synthetic-data end-to-end rehearsal remains required before enabling the staged Railway service.

## Current verified baseline and recovery runbook (2026-10-09)
- Baseline commit 7084b29e2bbf53bac5f6e8356dd8a6c35be1d08f: all five latest Actions succeeded. Synthetic rehearsal run 37975535647 exported customers/vehicles, encrypted with age, restored into a separate empty PostgreSQL database, and checked counts.
- This is a simplified synthetic schema, not a production-schema compatibility certificate.
- Expanded rehearsal adds two organizations, text/NULL fields, tenant-matched joins, rejection of nonempty target, wrong key, truncated ciphertext, wrong database identity, and failed source export with partial-file cleanup.
- Railway production service crm-clients-yandex-backup remains staged-create with no deployment. No production or existing backup configuration was changed.
- Connected Railway OAuth returns variable names only (valuesRedacted=true). The existing mirror has YANDEX_DISK_TOKEN, but this session cannot read it. The separate backup service has no token, database connection or age recipient. No live Yandex upload/download has been demonstrated.
- Retention deletion and alerts are not implemented for this separate backup. Do not activate until live synthetic upload/download and production-schema restore have passed.

### Disaster recovery procedure
This archive contains ONLY customers and vehicles. It does not replace the full CRM backup (organizations, bookings, users and the rest of the schema/data).

1. Preserve the damaged database and stop CRM writes under a separately authorized incident procedure. Never restore this archive directly over production.
2. Retrieve the selected .dump.age file from app:/clients-backups using the authorized Yandex account. Verify its recorded SHA-256 against the downloaded ciphertext. Current uploader checks size only; digest/readback verification is still required before rollout.
3. Retrieve the matching age private identity from offline custody. Never store it with the archive, in GitHub, or in Railway. Loss of this identity makes the encrypted backup unrecoverable.
4. Provision a disposable PostgreSQL database named crm_test_recovery or staging_recovery. Install the reviewed matching schema and prerequisite referenced records (for example organizations). Customers/vehicles must be empty. Match PostgreSQL tools to the archive/server versions.
5. Set the following environment variables without placing credentials into terminal history or logs:
   - CLIENT_BACKUP_ARCHIVE: downloaded encrypted file path
   - AGE_IDENTITY_FILE: offline identity file path
   - TEST_DATABASE_URL: connection to the disposable database
   - CLIENT_BACKUP_TEST_CONFIRM=ISOLATED
   - CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED=YES
   - CLIENT_BACKUP_EXPECTED_TEST_DB: exact disposable database name
6. Run: bash scripts/crm-client-backup-verify.sh
7. Require CLIENT_BACKUP_RESTORE_OK, then compare expected record counts, customer/vehicle ownership, organization boundaries and representative values. Check sequences for any sequence-backed IDs before permitting new writes. The current verification script checks customer links; it does not certify every production constraint or sequence.
8. Test CRM against the recovered isolated database. Only after incident approval promote a validated recovery or perform a reviewed transactional import. Preserve a rollback snapshot and verify public/admin CRM operations after the switch.
9. Remove plaintext temporary files and protect/reseal the offline private identity. Keep the ciphertext and incident verification record.

### Activation acceptance criteria
Reviewed real schema/dependencies; read-only export account; persistent offline key custody and key recovery rehearsal; synthetic live Yandex upload + download + digest + restore; exact record/value comparisons; failure notifications; validated retention policy; operator approval. Keep CLIENT_BACKUP_ENABLED=false until all criteria pass.

## Preparation packet: dedicated image, private transport, alerts (2026-10-09)

This section supersedes older statements above about size-only verification and missing alert code. It does NOT certify live Yandex access or the real database schema.

### Separate container
- `backup/Dockerfile`: PostgreSQL 18 client/server tool image with bash, age, curl, jq, Python and CA certificates. Runs as postgres (non-root); default entrypoint is the disabled backup job, not database initialization. The server tools are used ONLY by disposable synthetic tests.
- `backup/railway.toml`: dedicated Dockerfile configuration, restart NEVER, no active cron. Planned daily schedule is `35 3 * * *` UTC = 06:35 Moscow.
- No public domain, no production volume mount, no private decryption key in the image. Docker build context must never contain secrets. Image/package versions are to be recorded from the successful CI build; base digest pinning remains a deployment hardening step.

### Encryption keys
- `backup/key-setup.sh` must be run on a trusted operator machine: `CLIENT_BACKUP_OFFLINE_KEY_SETUP=YES bash backup/key-setup.sh /new/private/key-directory`.
- It refuses an existing directory, creates mode 700 directory and mode 600 files, never prints the identity. Keep `identity.agekey` offline with a second protected recovery copy; only public `recipient.txt` is configured as AGE_RECIPIENT.
- Test recovery using an artificial archive on that trusted machine. Record recipient fingerprint/key ID and custody location without recording the identity. This custody/recovery check has NOT yet been performed for a real production key.
- Use Railway sealed variables for Yandex/alert tokens when supported; otherwise private service variables with limited account access. Never paste tokens into chat, GitHub, Docker build args, logs or the image.

### Transport and integrity
- Existing Bash upload entrypoint delegates to `backup/yandex.py`.
- Only `app:/clients-backups` and distinct `app:/clients-backups-test` folders are allowed. Plaintext headers, symlinks, unsafe filenames, unrelated hosts, non-HTTPS URLs, credentials in URLs, alternative ports, public folders/files and redirects are refused.
- OAuth goes only to the fixed Yandex API; storage upload/download receives no OAuth header. Upload uses overwrite=false and bounded file size/timeouts.
- Success requires complete download of the uploaded ciphertext and exact SHA-256 equality, not size alone. Only then a SHA-256 custom property is recorded. No decrypt key is needed on Railway.
- Operator download: `python3 backup/yandex.py download clients-YYYYMMDDTHHMMSSZ.dump.age /private/new/archive.dump.age EXPECTED_SHA256` with CLIENT_BACKUP_ENABLED=true and the appropriate folder/token configured securely. This flag enables the invoked command, not a Railway cron by itself. Expected hash must come from a trusted verification record.
- The API tests and container rehearsal use a test double. They do not contact the real Yandex account. Real API behavior, granted app-folder scope, storage host compatibility and eventual consistency remain live acceptance checks.

### Failure monitoring
- Job failure exits nonzero and emits CLIENT_BACKUP_JOB_FAILED. Temporary ciphertext is cleaned. Export/decrypt/restore errors use generic messages to avoid record leakage from database/provider diagnostics.
- `backup/notify.py`: optional failure-only Telegram notification with fixed text and no raw logs, SQL, client records or credentials. Enable only on this new service with CLIENT_BACKUP_ALERTS_ENABLED=true, CLIENT_BACKUP_TELEGRAM_TOKEN and CLIENT_BACKUP_TELEGRAM_CHAT_ID. Existing alert services are not changed.
- Mock tests check the fixed payload, invalid token rejection, no network call when disabled, and preserved job failure status. Actual delivery is still unverified; no test message was sent.
- Missing-run monitoring is a separate acceptance requirement: alert if there has been no verified daily ciphertext for over 36 hours. Failure trap alone cannot detect a scheduler that never ran. No watchdog has been activated.

### Thirty-day retention (non-destructive preparation)
- Keep every backup younger than or exactly 30 days and ALWAYS keep the latest verified backup.
- `retention-plan` paginates only the dedicated folder and considers only exact filenames, paths and a verified SHA-256 marker. Unknown files, unverified uploads, directories and another backup system's files are preserved.
- Current implementation outputs candidate count only and NEVER calls DELETE. If no fresh verified upload exists, no deletion is permitted. Listing limits/errors fail closed.
- Future deletion must go to Yandex Trash (not permanent deletion), preserve a verified recovery copy, and require a separately reviewed implementation and acceptance test. 30-day automatic deletion is NOT enabled or implemented in this packet.

### Real schema audit and compatibility blockers
- `scripts/crm-client-schema-audit.sql` contains metadata-only inspection. Execute on an isolated restored CRM snapshot, not by modifying production. No real customer names, phones or VINs should enter the audit output.
- Exact columns, primary/foreign keys, organization dependencies, ID sequences, triggers/RLS, partitioning and PostgreSQL versions must be reviewed. This repository's initialization script covers staff authentication, not the full customers/vehicles schema.
- Known isolated restore service code uses customers(organization_id,name,phone), vehicles(organization_id,customer_id,make,model). This is incomplete evidence, not a schema inventory.
- Restore TOC now rejects anything beyond the two table data entries and reviewed conventional ID sequences. A real schema using other sequence names/partitions must be reviewed before adjusting this allowlist.
- Existing isolated backup service and working database remain unchanged. This session has no authorized SQL execution surface or readable credentials for them. Metadata audit has not been executed.

### Isolated recovery acceptance
- CI creates artificial rows, exports with pg_dump, encrypts with age, transports through an in-memory Yandex API double, downloads and hashes ciphertext, decrypts/restores into empty separate PostgreSQL and checks counts and organization ownership.
- Negative checks reject wrong keys, broken ciphertext, nonempty target, wrong database identity, invalid policy, failed export, unknown archive entries and cross-organization ownership.
- Wrong organization data is detected AFTER a transactional restore commits; the disposable target must be discarded on any verification failure. Never promote a failed target. This script does not repair production or automatically switch CRM connections.
- Before release compare full row digests/values, count and sequence behavior against the reviewed real schema. Restore the full CRM backup first when organizations/schema/other prerequisites are missing. Customer-only archives do not recover bookings, staff or full service history.

### Activation remains blocked
Live synthetic Yandex upload/download/restore; real schema/dependency audit; offline key custody/recovery; read-only source credentials; real notification delivery and missing-run monitoring; reviewed deletion implementation if needed; operator approval. Until then the dedicated Railway service remains staged, CLIENT_BACKUP_ENABLED=false, and has no active deployment or daily cron.
