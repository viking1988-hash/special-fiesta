# Client-only backup: data completeness and safe release decision

**Decision: NO-GO for production client-only backups.** The existing full-CRM
backups and their scheduled isolated restore checks remain operational and
must not be changed by this PR.

## Scope actually exported
`scripts/crm-clients-export.sh` runs `pg_dump --data-only` for exactly
`public.customers` and `public.vehicles`. This is an encrypted **subset
export**, not a standalone full CRM recovery point.

The export intentionally omits:
- Table definitions, constraints, indexes, functions and migrations.
- Organization/tenant parent rows and other referenced records.
- Other CRM data such as bookings, service history, messages and audit logs.
- Database roles, ACLs, ownership, and cluster-wide configuration.

Restoration therefore depends on a compatible, separately restored schema,
existing parent rows, verified row digests and tested sequences/foreign keys.
A successful age encryption, matching SHA-256 or an all-true JSON receipt
does **not** establish that customer records are independently recoverable.

## What is verified
- GitHub CI synthetic failure injection for pg_dump/age and existing-file
  overwrite protection, without real DB access.
- Isolated schema-only restore and artificial customer/vehicle round trip.
- Live wrapper preflight, output directory validation, and exclusive lock.
- Unauthenticated JSON recovery receipts are now explicitly reported as
  `UNVERIFIED_SELF_REPORTED_RECEIPT`, not `RECOVERY_VERIFIED`.

## Blockers before production activation
1. Verify production reader role and actual ACLs independently (read-only
   defaults alone do not prove least privilege).
2. Establish offline age identity custody and recovery by a separate operator.
3. Download a genuine encrypted archive from private remote storage and
   independently restore it into a fresh isolated, compatible database.
4. Validate customer and vehicle row digests, tenant boundaries, foreign keys,
   sequences and representative application reads.
5. Produce authenticated evidence tied to the exact archive hash and actual
   restore execution; do not rely on manually asserted JSON.
6. Review retention, privacy, encryption-key rotation and incident handling.
7. Require explicit launch approval after all evidence is reviewed.
8. Keep existing full-CRM S3/Yandex backup, restore test and alerts intact.

**Do not merge PR #12 or enable live client-only backup services merely
because GitHub Actions are green.**
