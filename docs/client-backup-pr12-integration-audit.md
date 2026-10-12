# Client backup PR #12 — integration and release safety audit

Status: **DRAFT / NOT DEPLOYABLE**. This PR adds checks and synthetic tests,
not a production client-backup service.

## Verified by CI
- Synthetic age encryption/decryption with temporary artificial records.
- Synthetic PostgreSQL export and isolated restore.
- Preflight configuration validation and refusal of privileged database roles.
- Archive metadata freshness and format validation.
- Receipt metadata checks, archive/receipt SHA-256 matching, and safe CLI failure.
- Production launch policy refuses authorization even when all boolean fields are true.

## Important limits (not covered by these PASS results)
1. `backup/archive_metadata_gate.py` validates **claimed** SHA-256 and privacy
   metadata; it does not fetch the remote object or compute its actual digest.
2. `backup/recovery_receipt_gate.py` validates **claimed** recovery fields; it
   does not authenticate the issuer or prove that a restore occurred.
3. `backup/recoverability_status.py` only correlates these claims and
   returns `UNVERIFIED_SELF_REPORTED_RECEIPT` for matching all-true metadata.
   It **never** establishes independently verified recovery.
4. `backup/production_launch_gate.py` always returns `NOT_AUTHORIZED`; it
   cannot grant production deployment approval.
5. `backup/live_export_preflight.py` is invoked by the optional
   `scripts/crm-clients-live-export-gated.sh` wrapper, **not** directly by
   `scripts/crm-clients-export.sh`. The wrapper is not deployed or scheduled;
   invoking the original script bypasses its extra policy checks.
6. The export script uses a shell pipeline. Synthetic failure injection,
   overwrite protection and age-header rejection are CI-tested, but this is
   not proof of a decryptable live archive. Independently verify snapshot
   consistency and restoration of sequence state for the real schema.
7. No independent evidence yet establishes the production DB reader's
   least-privilege grants, offline age identity recoverability, or
   isolated restoration of a real encrypted client archive.
8. Neither the optional customer-data exporter nor its watchdog is
   enabled/scheduled in production; keep them disabled.

## Required before any live activation
- Wire mandatory preflight into the **actual** export entrypoint, not just CI.
- Establish a dedicated restricted DB principal; independently test denied
  writes and unauthorized table reads.
- Verify an encrypted archive downloaded from private remote storage against
  its computed SHA-256, then restore it into a fresh isolated database.
- Produce authenticated, auditable recovery evidence from the restore
  process, not manually asserted JSON fields.
- Confirm sequence, foreign-key, row-digest, tenant and insertion checks.
- Review privacy, retention, key custody and an explicit production launch
  approval; do not rely on a green CI badge for approval.

## Existing services
Leave production PostgreSQL, full-CRM S3 backup, Yandex mirror, scheduled
restore test, and lead Telegram notifications unchanged.
