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

## Dual-recipient encryption status (Draft PR #13, 2026-10-22)
- The exporter and backup job require **both** `AGE_RECIPIENT_PRIMARY` and
  `AGE_RECIPIENT_RECOVERY`, each a distinct syntactically valid public age
  recipient. Missing, malformed, or identical recipients fail before `pg_dump`.
- The same ciphertext is encrypted to both public recipients; disposable CI
  identities independently decrypt it. No real offline private key is used in CI.
- Two independently held USB keys were verified in an owner-side **synthetic**
  recovery exercise; this does not prove real client archive recoverability,
  key custody durability, or authorization for production use.
- Legacy `AGE_RECIPIENT` is **not** an accepted replacement for either variable
  in this export path. Historical instructions mentioning it are superseded.
- GitHub CI PASS means synthetic code paths passed, not that a live service is
  deployed, production ACLs are correct, or the subset is independently restorable.

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

**Do not merge PR #12 or PR #13, or enable live client-only backup services merely
because GitHub Actions are green.**

## Scheduled job gate verification (Draft PR #13)
The scheduled client backup job now calls the live export wrapper rather than the low-level exporter directly. The wrapper checks an explicit live-run approval flag, preflight configuration, private output directory and exclusive lock before database export. CI includes a static regression test for this path. These checks do not authenticate operator approval or independently prove production database privileges and genuine archive recovery. Production remains NO-GO.

## CI verification and remaining launch gates (2026-10-23)
On Draft PR #13 commit `db59a57997723b24bc98f8b60390331b9c091b96`, all five GitHub Actions workflows completed successfully: authentication, PostgreSQL integration, export preflight, synthetic restore rehearsal, and client backup checks. These are **synthetic/CI checks**, not production evidence. The wrapper also now resolves Python modules from the repository root when invoked from another working directory, and the live output gate rejects malformed archive prefixes.

**Release decision remains NO-GO:** production reader privileges, real encrypted archive restore in an isolated environment, authenticated evidence, data completeness, retention/privacy approval, and explicit owner launch authorization have not been independently established by these tests. Do not merge or enable the scheduled job based on CI alone.

## Latest code-review checkpoint (2026-10-23)
Draft PR #13 HEAD `0b07fd87492b170d609bdb1056da16d78167946f` passed all five GitHub Actions workflows: CRM auth checks, CRM PostgreSQL integration, CRM client export preflight tests, CRM synthetic client restore rehearsal, and CRM client backup checks. This includes regressions for exact Yandex API OAuth destination matching, dangling archive symlinks, and rejection of ambiguous PostgreSQL connection URLs. A prior syntax error in the URL preflight was fixed before this green run.

**CODE: candidate for independent review, not a security certification. PRODUCTION: NO-GO.** A syntactically valid age header does not authenticate ciphertext; a self-reported recovery receipt does not authenticate restore provenance. Real archive recovery, production reader ACLs, data/schema completeness, privacy and retention approvals, and explicit owner authorization remain outstanding. Keep this PR Draft; do not merge, deploy, enable schedules, or access real customer records on the strength of CI.

## Restore rehearsal fidelity limits
The disposable container rehearsal creates only simplified `customers` and `vehicles` tables, with synthetic rows and a local trusted PostgreSQL server. It checks both age identities, row round-trip and a schema audit; it does **not** reproduce production migrations, tenant parent tables, role permissions, triggers, full foreign-key graph, or application-level recovery. It therefore cannot establish that the two-table data-only dump restores into a clean production-equivalent CRM database. Independent production-schema-compatible isolated restore is a hard prerequisite before launch.

## Restore target restriction (2026-10-23)
The repository's `scripts/crm-client-backup-verify.sh` now refuses remote PostgreSQL server addresses even when `CLIENT_BACKUP_REMOTE_TEST_APPROVED=YES` is set. The supported synthetic verification path requires a local disposable database. Loopback addressing alone does not prove the underlying instance is disposable (for example, a forwarded port could reach another server); operators must independently establish process/container isolation before any restore. No genuine customer archive restore is authorized by this change.

## Verified synthetic checkpoint and remaining trust boundary (2026-10-23)
Draft PR #13 HEAD `836fccaa2914ca4eab3e57e8d2de106b8439a899` completed all five GitHub Actions workflows successfully, including PostgreSQL 18 container rehearsal and the negative test for a mismatched cluster system identifier. This is a synthetic CI result only.

The restore verifier now requires `CLIENT_BACKUP_EXPECTED_CLUSTER_ID` and compares it with `pg_control_system().system_identifier` before invoking `pg_restore`. The expected value must be established independently from the disposable PostgreSQL instance during provisioning; copying it from an arbitrary connection string would defeat this control. Cluster ID matching and loopback address checks do not establish that a server is disposable or exclude an SSH/port-forwarded remote database. An operator must independently attest to the instance/container identity, network isolation, fresh schema and absence of real data. Do not run the restore against a forwarded port or any production/staging database.

**Release gate remains NO-GO.** Before enabling live client-only backups, perform an authorized production-schema-compatible isolated recovery rehearsal, independently validate production reader ACLs, custody of both recovery identities, encrypted archive provenance and row-level/tenant integrity, and obtain explicit owner and privacy/retention approval. No live backup job or production restoration is authorized by these synthetic tests.
