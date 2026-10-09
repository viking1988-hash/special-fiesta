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
