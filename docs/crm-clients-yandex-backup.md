# Separate encrypted customers/vehicles backup: verified status and recovery

Updated 2026-10-09 UTC. Repository `viking1988-hash/special-fiesta`, branch `feature/crm-personal-auth`, PR #9. **Production backup is not enabled and is not yet ready for approval.** Earlier preparation notes are superseded by this report.

## Evidence of completed tests

Code commit: `c13cc1e8d20f1665b8ae0e7ba675b1181df4f3c3`.

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

- Live source pinned to the tested code commit above; documentation pushes do not redeploy it.
- Dockerfile: `backup/Dockerfile.rehearsal`; start: `bash /app/test/backup/container-rehearsal.sh`.
- Restart policy NEVER. No active cron, public domain, TCP proxy or volume mount.
- No production database connection or production age identity/recipient configured.
- After the completed one-shot test, `CLIENT_BACKUP_ENABLED=false` and `CLIENT_BACKUP_LIVE_YANDEX_TEST=false` were set with deploys skipped. These settings apply on the next deployment; the completed test process is not restarted. A manual redeploy would run only the artificial local rehearsal with mock transport.
- Alerts remain disabled. Test path remains `app:/clients-backups-test`.

`backup/Dockerfile` is the prepared production-job image; it has a disabled default entrypoint. Do not replace the rehearsal configuration or enable the production job before all acceptance gates below pass and the owner gives separate approval.

## Container and security audit

Pinned base image: PostgreSQL 18 digest `sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873`. Observed CI tools: PostgreSQL 18.6, age 1.3.2, curl 8.22.0, jq 1.8.2, Python 3.14.8. Runs as postgres, not root. `.dockerignore` excludes environment files, keys, dumps and other secret-bearing artifacts.

- Export requires explicit enabled/schema/encryption gates, uses a read-only session and Bash pipefail; failed pg_dump cannot become a successful backup. Only public.customers/public.vehicles data is selected. Ciphertext is created with restricted permissions; no intermediate plaintext export is retained.
- OAuth is sent only to the fixed Yandex API. Storage requests do not carry it. URLs require HTTPS, approved hosts and port, without userinfo/fragments. Symlinks, unsafe filenames, plaintext archive headers and excessive size are rejected.
- Dedicated app-folder allowlist, timestamped names, overwrite=false. Upload success requires full ciphertext readback and exact SHA-256, then a verification custom property. Download requires a trusted expected SHA-256 and refuses an existing destination.
- Restore requires an explicitly named empty isolated database, loopback server or separately approved remote isolated host, restricted identity permissions and a reviewed archive TOC. Only the two table-data entries and conventional ID sequence entries are accepted. Restore is transactional; errors use generic diagnostics to avoid personal data leakage.
- Post-restore orphan/cross-organization validation can fail AFTER the transaction commits. Discard any failed disposable target; never promote it.
- Negative tests exercise failed export cleanup, wrong identity/key, damaged ciphertext, nonempty target, wrong target database, unexpected entries and cross-organization links. This is not a certificate of compatibility with the real CRM schema.

## Encryption key custody

Production key generation and custody have NOT been completed. Do not generate the production private identity in Railway, the repository or alongside the remote archive.

On a trusted operator machine with age installed:

```
CLIENT_BACKUP_OFFLINE_KEY_SETUP=YES bash backup/key-setup.sh /new/private/key-directory
```

The script refuses an existing directory, creates directory mode 700 and files mode 600, and never prints the identity. Keep `identity.agekey` offline with a second protected recovery copy; configure only public `recipient.txt` as AGE_RECIPIENT on the new service. Record the public recipient/key ID and custody location without recording the private key. Rehearse recovery of an artificial archive using the recovered offline copy before production approval. Lost private identity means unrecoverable ciphertext.

Use private/sealed Railway variables for OAuth and alert credentials with restricted account access. Never put credentials into chat, shell history, GitHub, Docker build arguments or logs.

## Real schema audit: still required

The real table structure has NOT been inspected. Existing isolated restore-service code establishes basic names and relationships: customers has organization_id/name/phone; vehicles has organization_id/customer_id/make/model. This is incomplete metadata, not a column/constraint inventory.

`scripts/crm-client-schema-audit.sql` is ready and tested against artificial tables. Execute it read-only on an authorized isolated restored CRM snapshot; keep the output limited to metadata. Review exact columns/types, foreign keys and prerequisite organizations, sequence names, RLS/triggers, partitions and server/tool versions. The repository initialization script covers staff authentication, not the full client schema. Rehearse export and restore against that reviewed schema and prerequisite records with artificial rows before enabling production.

No direct SQL access or readable credentials for the isolated existing snapshot were available through the connected tools; this audit was not substituted with guesses or a production connection. Do not change the existing restore/backup service to obtain access.

## Error control and notifications

The job exits nonzero and emits CLIENT_BACKUP_JOB_FAILED on failure, cleans temporary ciphertext and preserves the original failure status. `backup/notify.py` prepares fixed-text Telegram failure messages without raw errors, client records or credentials. Mock tests verify payload, invalid credential rejection, disabled no-network behavior and preserved job failure status. No real notification was sent; actual delivery remains an acceptance gate.

On the new service only, securely configure CLIENT_BACKUP_TELEGRAM_TOKEN / CLIENT_BACKUP_TELEGRAM_CHAT_ID, then explicitly enable CLIENT_BACKUP_ALERTS_ENABLED for an artificial failure test. Record receipt without publishing credentials.

`backup/watchdog.py` prepares a separate read-only freshness check: alert when no verified backup exists within 36 hours. It is disabled by default via CLIENT_BACKUP_MONITOR_ENABLED. Mock tests cover fresh/stale/missing/future archives. Actual scheduling and notification delivery for this monitor remain unverified. A job failure trap alone cannot detect a scheduler that never ran.

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
6. Compare expected customers/vehicles counts, full row digests, foreign keys, organization boundaries and sequence behavior. Run CRM checks against the isolated recovered database. The synthetic test demonstrated this flow for its simplified schema only; real-schema acceptance remains pending.
7. After separate incident approval, promote the validated recovery or perform a reviewed transactional import with a rollback snapshot. This script does not switch CRM connections or repair production automatically.
8. Remove temporary plaintext and reseal the offline identity. Retain ciphertext and the verification record. Do not delete the last working recovery copy.

## Remaining release gates

- Metadata-only audit of an authorized isolated real-schema snapshot and artificial-data recovery against that schema.
- Read-only production export account scoped to the reviewed tables/dependencies; no write privileges.
- Offline production key custody, second protected copy and demonstrated key recovery.
- Real failure notification and missing-run monitoring delivery tests.
- If automatic deletion is required: reviewed implementation and artificial-folder tests; current mode only plans retention.
- Reviewed production Dockerfile/source/variables and schedule, followed by the owner's explicit approval after all checks.

The live synthetic Yandex roundtrip is complete. The service is ready for further safe preparation, **not for backing up real customers**. Keep CLIENT_BACKUP_ENABLED=false and cron absent. Rollback preparation by reviewed backup-only reverts in PR #9; no production database rollback is required. Do not merge the wider feature branch or alter other services as part of this preparation.
