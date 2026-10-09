# Separate encrypted customers/vehicles backup: verified status and recovery

Updated 2026-10-09 UTC. Repository `viking1988-hash/special-fiesta`, branch `feature/crm-personal-auth`, PR #9. **Production backup is not enabled and is not yet ready for approval.** Earlier preparation notes are superseded by this report.

## Evidence of completed tests

Original live-Yandex code commit: `c13cc1e8d20f1665b8ae0e7ba675b1181df4f3c3`. Continued from documentation commit `2f4856e4998ac3507276220e6538e650afed3d23`. Previous tested baseline: `f2a6ed8001831433d99aefbe92e74d6b5695673e`. Latest reader-role/watchdog code: `210dc1f5368ebba6bb7fe48d7a93b4c4c91e893f`; all five Actions succeeded, including backup checks 37984255579. Latest suite: 32 passing tests. See [current role/watchdog report](crm-backup-role-watchdog-report-20261009.md), [owner key procedure](crm-backup-offline-key-owner.md) and [inactive rollout plan](crm-backup-launch-plan.md). All five Actions succeeded there, including backup checks 37982072623 and restore rehearsal 37982072616; the expanded unit/mock suite has 25 passing tests. Live real-schema/key/alert evidence is in [the verification report](crm-backup-verification-20261009.md) and [timestamped metadata-only logs](evidence/crm-backup-20261009.json).

All five Actions succeeded at this commit: CRM client backup checks (37980025900), synthetic client restore rehearsal (37980025862), PostgreSQL integration (37980026178), CRM auth (37980025883), Jarvis runtime (37980025936). Backup safety suite: 22 passing unit/mock tests. Container tests build both dedicated images and exercise the disabled production entrypoint, non-root tools and isolated synthetic recovery.

Real Railway rehearsal deployment: `42dd5686-2a14-4e40-baee-3ec8a2b2181f`, created 2026-10-09T19:25:56.149Z, service `crm-clients-yandex-backup`. Runtime evidence, beyond the platform SUCCESS status:

```
CLIENT_BACKUP_ENCRYPTED_OK
SYNTHETIC_LIVE_YANDEX_READBACK_OK bytes=1623 sha256=0eadacba184ccee1e16f8f3dd87b0b2626b64f7d308d091a96fdba7d7823949d
CLIENT_BACKUP_RESTORE_OK
CONTAINER_SYNTHETIC_METADATA_AUDIT_OK
CONTAINER_SYNTHETIC_RECOVERY_OK
SYNTHETIC_REHEARSAL_DONE customers=2 vehicles=2 links=2
```

The container created two loopback-only disposable PostgreSQL databases, inserted artificial records only, exported customers/vehicles, encrypted with an ephemeral age identity, uploaded ciphertext to `app:/clients-backups-test`, downloaded and SHA-256 checked it, decrypted and restored into the other empty database. Both table row digests matched source; counts and organization-matched links matched. Synthetic metadata audit also passed. Temporary identity, decrypted dump and local database process are removed on exit. The test identity is not a production key and the remote rehearsal archive is not a usable production backup.

Earlier live runs exposed two transport compatibility failures: Yandex supplied `downloader.disk.yandex.ru`, then redirected its download to storage. Fixes allow that exact download host and at most three credential-free GET redirects to validated HTTPS storage hosts. API and PUT upload redirects remain rejected. Safety tests cover unsafe destinations, header stripping, redirect limits and PUT rejection. Failed attempts may have left unverified encrypted artificial files in the test folder; no automatic deletion was performed.

No real customer data was uploaded. No production CRM database, working CRM service, existing full backup, mirror configuration or existing alert service was changed. The new service uses the existing mirror token through a Railway variable reference; the token value was neither read nor printed.

## Current Railway configuration

Project `Avtohirurg-CRM`; project ID `3324700c-193f-46f0-aca7-719ac6cb14f6`; new service ID `2c914871-74c5-4837-bb94-b4620b50b934`.

- Both new services pinned to `210dc1f5368ebba6bb7fe48d7a93b4c4c91e893f`; documentation pushes do not redeploy them. Backup uses the disabled schema-rehearsal image; separate crm-clients-backup-watchdog uses backup/Dockerfile.watchdog. No new cron exists; both restart policies are NEVER.
- Dockerfile: `backup/Dockerfile.schema-rehearsal`; start: `python3 /app/test/backup/schema-rehearsal.py`. Includes aws-cli for read-only snapshot retrieval during explicitly gated rehearsals.
- Restart policy NEVER. No active cron, public domain, TCP proxy or volume mount.
- No production database connection or production age identity/recipient configured.
- After tests, CLIENT_BACKUP_ENABLED, CLIENT_BACKUP_SCHEMA_REHEARSAL, CLIENT_BACKUP_LIVE_ALERT_TEST, CLIENT_BACKUP_LIVE_YANDEX_TEST and CLIENT_BACKUP_ALERTS_ENABLED were all set false. Temporary AWS credentials/bucket/endpoint references on the new service were cleared. A final deployment verifies SCHEMA_REHEARSAL_DISABLED, without fetching a snapshot or sending another message.
- Alerts remain disabled. Test path remains `app:/clients-backups-test`.

`backup/Dockerfile` is the prepared production-job image; it has a disabled default entrypoint. Do not replace the rehearsal configuration or enable the production job before all acceptance gates below pass and the owner gives separate approval.

## Container and security audit

Pinned base image: PostgreSQL 18 digest `sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873`. Observed CI tools: PostgreSQL 18.6, age 1.3.2, curl 8.22.0, jq 1.8.2, Python 3.14.8. Runs as postgres, not root. `.dockerignore` excludes environment files, keys, dumps and other secret-bearing artifacts.

- Export requires explicit enabled/schema/encryption gates, uses a read-only session and Bash pipefail; failed pg_dump cannot become a successful backup. Only public.customers/public.vehicles data is selected. Ciphertext is created with restricted permissions; no intermediate plaintext export is retained.
- OAuth is sent only to the fixed Yandex API. Storage requests do not carry it. URLs require HTTPS, approved hosts and port, without userinfo/fragments. Symlinks, unsafe filenames, plaintext archive headers and excessive size are rejected.
- Dedicated app-folder allowlist, timestamped names, overwrite=false. Upload success requires full ciphertext readback and exact SHA-256, then a verification custom property. Download requires a trusted expected SHA-256 and refuses an existing destination.
- Restore requires an explicitly named empty isolated database, loopback server or separately approved remote isolated host, restricted identity permissions and a reviewed archive TOC. Only the two table-data entries and conventional ID sequence entries are accepted. Restore is transactional; errors use generic diagnostics to avoid personal data leakage.
- Post-restore orphan/cross-organization validation can fail AFTER the transaction commits. Discard any failed disposable target; never promote it.
- Negative tests exercise failed export cleanup, wrong identity/key, damaged ciphertext, nonempty target, wrong target database, unexpected entries and cross-organization links. Actual schema compatibility was subsequently tested using the 2026-10-09 snapshot and artificial records; later schema changes require a fresh audit.

## Encryption key custody

Production key generation and custody have NOT been completed. A disposable artificial-key rehearsal passed: directories 700, identities 600, rejection of 644, removal of the active copy, recovery from a second copy, equal public recipient and successful decryption. Actual customer/vehicle artificial-row recovery also used the recovered test identity after the active copy was removed. Both copies were temporary and destroyed; two copies on one container are not proof of offline custody or protection against host loss. Do not generate the production private identity in Railway, the repository or alongside the remote archive.

On a trusted operator machine with age installed:

```
CLIENT_BACKUP_OFFLINE_KEY_SETUP=YES bash backup/key-setup.sh /new/private/key-directory
```

The script refuses an existing directory, creates directory mode 700 and files mode 600, and never prints the identity. Keep `identity.agekey` offline with a second protected recovery copy; configure only public `recipient.txt` as AGE_RECIPIENT on the new service. Record the public recipient/key ID and custody location without recording the private key. Rehearse recovery of an artificial archive using the recovered offline copy before production approval. Lost private identity means unrecoverable ciphertext.

Use private/sealed Railway variables for OAuth and alert credentials with restricted account access. Never put credentials into chat, shell history, GitHub, Docker build arguments or logs.

## Real schema audit: verified against an isolated snapshot

Read-only S3 retrieval of `crm-20261009-023155.dump`, modified 2026-10-09T02:31:56Z (05:31:56 Moscow). SHA-256: `fb347019c47c07490f4586c341d922606aa83c4060d5b769d2a7cc7520e07310`. The new disposable container restored only SCHEMA into two loopback databases. Both tables were verified empty before artificial inserts; the downloaded full archive was removed. No real row data was restored, queried or uploaded. Existing restore service was unchanged.

- customers: id, organization_id, name, phone, email, created_at, consent_personal_data_at. Required: id/organization_id/name/phone/created_at. Unique organization_id+phone; FK to organizations; sequence customers_id_seq.
- vehicles: id, organization_id, customer_id, make, model, year, plate, vin, created_at, mileage. Required: id/organization_id/make/model/created_at. customer_id is nullable; FKs to customers and organizations; mileage NULL or >=0; sequence vehicles_id_seq.
- Both are ordinary unpartitioned tables with no user triggers or RLS enabled in this snapshot. Numeric/date precision, indexes and incoming references were also inventoried. bookings, work_orders and customer_contact_events depend on these tables; the two-table archive does not recover those records.
- Artificial source: two organizations, two customers, three vehicles (one unassigned). Required fields, NULLs, fixed timestamps and both tenants were exercised. Duplicate phone within one tenant, nonexistent customer FK and negative mileage were rejected by the real constraints. The same artificial phone in two organizations was allowed.
- Encrypted export restored into the other empty database with matching synthetic organizations. Both complete-row digests matched, counts 2/3, matched tenant links 2, unassigned vehicles 1. Sequence last_value/is_called matched, including gaps from rejected inserts, and new customer/vehicle writes succeeded without ID collision.

This proves compatibility with the schema in that snapshot, not freshness against uninspected later production migrations. Production CRM connectivity, credentials and read-only export-role deployment were not changed.

## Error control and notifications

The job exits nonzero and emits CLIENT_BACKUP_JOB_FAILED on failure, cleans temporary ciphertext and preserves the original failure status. `backup/notify.py` prepares fixed-text Telegram failure messages without raw errors, client records or credentials. Mock tests verify payload, invalid credential rejection, disabled no-network behavior and preserved job failure status. Actual failure-trap delivery passed in deployment 573adc16-6bfc-414d-8d8f-a0d8b44337dd. The job deliberately failed its schema gate before any export, exited 1 and sent one clearly marked TEST message. Telegram returned ok=true with message_id=24 and the expected chat ID; no token/chat value was printed. This establishes API-confirmed delivery into the configured chat, not proof a person read it.

The new service has protected references to the existing monitor bot/chat variables; the monitor itself was not changed or restarted. CLIENT_BACKUP_LIVE_ALERT_TEST is now false, so redeploying does not resend the test. Actual production failure alerts remain disabled until rollout approval.

`backup/watchdog.py` prepares a separate read-only freshness check: alert when no verified backup exists within 36 hours. It is disabled by default via CLIENT_BACKUP_MONITOR_ENABLED. Mock tests cover fresh/stale/missing/future archives. An actual one-shot read-only test on the artificial Disk folder passed: fresh metadata succeeded, clock +37 hours caused failure and Telegram accepted test message 25. Independent periodic scheduling remains disabled and has not run. A job failure trap alone cannot detect a scheduler that never ran.

## Schedule and 30-day retention policy

Prepared schedule: `35 3 * * *` UTC, 06:35 Moscow, daily. It is commented in `backup/railway.toml`; no Railway cron is active.

Keep all verified backups aged at most 30 days and always preserve the latest verified copy. Only exact archive names in the dedicated production folder may be considered. Preserve unknown files, directories, unverified uploads and every file belonging to the existing backup. No deletion may follow a failed/unverified new upload.

`retention-plan` paginates with limits and produces a candidate count; it NEVER calls DELETE. Automatic 30-day removal is not implemented or enabled. Any later implementation must use Trash, preserve a verified recovery copy and pass artificial-folder deletion tests before separate approval. Existing backups remain untouched.

## Disaster recovery runbook

This archive contains ONLY customers and vehicles. It cannot recover organizations, appointments, users, full service history or the rest of CRM by itself. Preserve the existing full backup system.

1. Preserve the damaged database and stop CRM writes under the separately authorized incident procedure. Never restore this archive over the running production database.
2. Restore the full CRM backup into an isolated recovery environment when schema or prerequisite records are missing. Install the reviewed matching schema and prerequisites; the two target tables must be empty. Match PostgreSQL client/server versions and review every schema dependency and sequence.
3. Select a verified ciphertext in `app:/clients-backups`; obtain its SHA-256 from a trusted verification record. Download into a new private destination using `python3 backup/yandex.py download clients-YYYYMMDDTHHMMSSZ.dump.age /private/new/archive.dump.age EXPECTED_SHA256` with securely configured token/path and CLIENT_BACKUP_ENABLED=true for that operator command. This flag does not enable Railway scheduling. The downloader checks size, encrypted header and SHA-256.
4. Retrieve the matching offline age identity. Set these variables securely without credential logging or terminal history:
   - CLIENT_BACKUP_ARCHIVE: downloaded ciphertext path
   - AGE_IDENTITY_FILE: private identity path, mode 600 or 400
   - TEST_DATABASE_URL: isolated recovery database connection
   - CLIENT_BACKUP_TEST_CONFIRM=ISOLATED
   - CLIENT_BACKUP_TEST_DB_EMPTY_CONFIRMED=YES
   - CLIENT_BACKUP_EXPECTED_TEST_DB: exact name, e.g. crm_test_recovery
   - CLIENT_BACKUP_REMOTE_TEST_APPROVED=YES only for a separately verified remote isolated server; loopback requires no such override.
5. Run `bash scripts/crm-client-backup-verify.sh`. Require CLIENT_BACKUP_RESTORE_OK; discard the target on any failure. Never weaken archive or database identity guards to make a restore pass.
6. Compare expected customers/vehicles counts, full row digests, foreign keys, organization boundaries and sequence behavior. Run CRM checks against the isolated recovered database. Artificial-record recovery passed on the reviewed real snapshot schema; re-audit any later migrations before recovery or rollout.
7. After separate incident approval, promote the validated recovery or perform a reviewed transactional import with a rollback snapshot. This script does not switch CRM connections or repair production automatically.
8. Remove temporary plaintext and reseal the offline identity. Retain ciphertext and the verification record. Do not delete the last working recovery copy.

## Remaining release gates

- Install/authenticate the production reader role through trusted DBA access. SQL and actual write-denial/export tests passed in an isolated copy; the production catalog and credentials were not changed.
- Offline production key custody, second protected copy and demonstrated key recovery.
- Actual activation and observation of the independently scheduled monitor after rollout approval; the one-shot missing-run notification test and actual job failure notification have passed.
- If automatic deletion is required: reviewed implementation and artificial-folder tests; current mode only plans retention.
- Reviewed production Dockerfile/source/variables and schedule, followed by the owner's explicit approval after all checks.

The live synthetic Yandex roundtrip is complete. The service is ready for further safe preparation, **not for backing up real customers**. Keep CLIENT_BACKUP_ENABLED=false and cron absent. Rollback preparation by reviewed backup-only reverts in PR #9; no production database rollback is required. Do not merge the wider feature branch or alter other services as part of this preparation.
