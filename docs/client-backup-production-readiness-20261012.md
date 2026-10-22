# CRM client-data backup: production readiness gate (2026-10-12)

Status: **NOT ENABLED**. This is a review checklist, not deployment approval.

## Verified current configuration
- Railway `crm-clients-yandex-backup` runs `python3 /app/test/backup/schema-rehearsal.py` from `backup/Dockerfile.schema-rehearsal`; it is an isolated **synthetic/schema rehearsal**, not a production customer-data exporter.
- Railway `crm-clients-backup-watchdog` runs `python3 /app/backup/watchdog.py` from `backup/Dockerfile.watchdog`. Last log: `CLIENT_BACKUP_MONITOR_DISABLED`.
- Neither service has a Railway cron schedule. The Dockerfiles default their enable flags to false.
- The existing full-CRM backup to S3 and Yandex mirror is a **separate working path**. Do not change it while building this optional customer-data backup.
- Tests of encryption, isolated restore, row digests, sequences, and Telegram outage simulation use artificial data and do **not** establish production readiness.

## 2026-10-22 follow-up: dual independent recipients

Draft PR #13 requires both `AGE_RECIPIENT_PRIMARY` and
`AGE_RECIPIENT_RECOVERY`, distinct syntactically valid public AGE keys.
Synthetic tests independently decrypt the same ciphertext with two ephemeral
identities. A single identity copied onto two USB drives is **not** sufficient.
The existing owner-only script and older documentation describe copies of
one identity and are historical; do not overwrite previously tested keys.

**Outstanding live evidence:** production database reader effective ACLs
verified independently; source schema/tenant/sequence compatibility;
actual encrypted archive retrieved from approved private storage and restored
into a fresh isolated database; hash-bound authenticated recovery evidence;
privacy/retention approval and explicit owner production authorization.
Until then keep `CLIENT_BACKUP_ENABLED=false`, cron absent, existing full-CRM
backup untouched, and the launch gate at `NOT_AUTHORIZED`.

## Required implementation and evidence before enablement
1. Define exact scope: `customers`, `vehicles`, their relationships, organization tenancy, and sequence state. Avoid exporting unrelated CRM records.
2. Create a dedicated read-only DB principal with `SELECT` only on the approved tables and sequences. Review grants and revoke inherited privileges. Never use production superuser credentials in the exporter.
3. Establish an authenticated private Railway-to-PostgreSQL connection; verify `SELECT` works and `INSERT`, `UPDATE`, `DELETE`, DDL, privilege escalation, and other CRM tables are denied.
4. Confirm the export script is compatible with the real schema, null values, foreign keys, tenant boundaries, sequence states, and a consistent PostgreSQL snapshot.
5. Encrypt locally **before** network upload; use an independently held age recovery identity, a pinned recipient, and restricted file permissions. Do not print customer rows, decrypted payloads, DB URLs, tokens, or private keys in logs.
6. Upload only encrypted files to the dedicated Yandex Disk path; use unique timestamped filenames, verify remote size/hash where supported, and prevent accidental overwrites.
7. Implement explicit retention and deletion guards, with a dry-run listing and evidence of at least one retained recoverable archive. Never delete the only good copy.
8. Implement a separately scheduled exporter with bounded retries, lock/idempotency, timeouts, and nonzero exit codes. Do not repurpose the schema-rehearsal service as the live exporter.
9. Implement an independently scheduled read-only freshness watchdog that checks actual remote encrypted archives. Verify alerts on a controlled failure, and recovery notifications without duplicate alert storms.
10. Prove recovery into a new isolated database with the offline-held key. Compare record digests, relationships, tenant IDs, sequences, and the ability to insert after restore. Do not restore into production.
11. Verify Telegram destination and delivery with a clearly labeled test message; record its message ID. Do not send customer data.
12. Review personal-data retention, access, audit, key rotation, and deletion requirements before production launch.

## Rollout order
- Review the above with the responsible owner; implement and test on a new branch and isolated staging resources.
- Confirm successful CI and isolated recovery; require explicit approval for production credentials and cron enablement.
- Enable one controlled encrypted backup, independently verify it, then enable scheduled exports and the watchdog.
- Preserve the existing full-CRM S3/Yandex backup and monitor throughout; roll back by disabling only the new services.

## Stop conditions
Missing read-only role, missing independently recoverable key, any plaintext upload, unverifiable remote archive, incorrect tenancy, failed isolated restore, or unverified alert delivery => **NO GO**.
