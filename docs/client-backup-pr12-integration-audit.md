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
3. `backup/recoverability_status.py` only correlates these claims. Its
   `RECOVERY_VERIFIED` return is **metadata-policy verified**, not proof of
   real recovery. Do not surface it as a production recovery guarantee.
4. `backup/production_launch_gate.py` always returns `NOT_AUTHORIZED`; it
   cannot grant production deployment approval.
5. `backup/live_export_preflight.py` is not invoked by
   `scripts/crm-clients-export.sh`. Passing its tests does **not** enforce
   those gates in the actual export path.
6. The current export script uses a shell pipeline. Before production use,
   independently test failure behavior, snapshot consistency, and restore
   of sequence state for the real schema.
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
