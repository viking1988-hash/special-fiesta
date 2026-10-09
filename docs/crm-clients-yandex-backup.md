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
