# Client backup watchdog — guarded rollout

Status: **NOT ENABLED**. This document is a read-only operational plan; it does not authorize a production rollout.

## Confirmed 2026-10-11

- Railway service `crm-clients-backup-watchdog` is in the `production` environment, with latest deployment SUCCESS but no cron schedule.
- `backup/watchdog.py` exits successfully with `CLIENT_BACKUP_MONITOR_DISABLED` unless `CLIENT_BACKUP_MONITOR_ENABLED` is exactly `true`.
- `backup/Dockerfile.watchdog` defaults monitoring and alerts to false.
- `backup/railway-watchdog.toml` has an intentionally commented hourly cron (`5 * * * *`) pending rollout approval.
- Previous logs contain both failed freshness checks and a successful check, followed by `CLIENT_BACKUP_MONITOR_DISABLED`.
- The connected Railway API exposes variable names, not values. Test/isolation settings cannot currently be verified.

## Release gates

1. Confirm whether the target is a synthetic rehearsal or the intended live client-backup watchdog. Record the operator-approved environment and service.
2. Verify the current values of `SYNTHETIC_REHEARSAL_ONLY`, `CLIENT_BACKUP_LIVE_WATCHDOG_TEST`, `CLIENT_BACKUP_MONITOR_ENABLED`, and `CLIENT_BACKUP_ALERTS_ENABLED` in Railway without copying credentials into logs or issues.
3. Confirm the actual client backup job is scheduled, encrypted, and uploading verified archives to the expected private Yandex Disk path.
4. Validate a fresh verified archive (maximum 36 hours old) using read-only checks.
5. Confirm a controlled alert-delivery test in the correct destination; do not send an unlabelled live alert from a rehearsal.
6. Record the previous cron/variable values for rollback. Only then enable the approved schedule and monitoring in the correct environment.
7. Confirm at least two scheduled executions and their actual `CLIENT_BACKUP_FRESHNESS_OK` logs. Do not treat Railway deployment SUCCESS as proof of monitoring.
8. Verify alert failure paths and report any missing delivery evidence.

## Rollback

Restore the prior schedule and monitoring flag values, verify the new deployment has settled, and check its logs. Never delete backup archives or change CRM databases as part of this rollout.

## Known caveat

The current Python program returns exit code 0 when monitoring is disabled. An operational dashboard must explicitly distinguish **disabled** from **healthy**.

## Operator verification worksheet (no secret values)

- [ ] Confirm Railway project, `production` environment, and exact service ID before any change.
- [ ] Confirm that the intended live watchdog is **not** a synthetic rehearsal. If ambiguous, stop.
- [ ] In Railway UI, record only boolean status (not secret contents) for monitoring, alerts, live test, and synthetic rehearsal switches.
- [ ] Verify a fresh, independently encrypted **client** archive in `app:/clients-backups`; the general CRM dump alone is not proof of a separate client archive.
- [ ] Confirm the expected Telegram recipient and that controlled test messages are clearly labeled.
- [ ] Confirm that cron `5 * * * *` (UTC) is acceptable for production; no scheduling change before approval.
- [ ] Capture prior settings privately for rollback, without putting tokens in GitHub.
- [ ] After an approved rollout, confirm two real cron runs and failure-notification evidence.

**Stop conditions:** unknown environment, redacted/unknown test flag values, missing client archive, missing alert destination, or unclear rollback path. Do not infer green health from `SUCCESS` alone.
