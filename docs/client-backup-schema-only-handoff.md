# Schema-only source: independent handoff and E2E evidence

Status: **NOT APPROVED FOR PRODUCTION**. This document is a checklist, not proof that a schema-only source exists.

## 1. Prepare an approved source (outside Production)

Use an authorized, isolated schema-equivalent database with **no customer records**. Generate a new PostgreSQL custom-format **schema-only** archive using `pg_dump --schema-only --format=custom`. Do not download or repurpose a full CRM backup as a substitute. Never put passwords, private age identities or customer rows in the repository, CI logs or issue comments.

Record the archive SHA-256, PostgreSQL major version, migration/commit reference, creation date, approving operator and the approved private object key `crm-schema-only-YYYYMMDD-HHMMSS.dump`. Keep the archive private. An object name, `CLIENT_BACKUP_SCHEMA_ONLY_SOURCE_REVIEWED=YES` flag, or checksum alone does not prove content safety.

Before any upload or rehearsal, an independent reviewer must inspect `pg_restore --list <archive>` **offline**. Reject any archive containing `TABLE DATA`, `BLOBS`, `BLOB`, `LARGE OBJECT`, or `MATERIALIZED VIEW DATA` entries. This is a structural check, not a guarantee that SQL definitions or comments contain no sensitive literals; inspect those separately. Record a second operator's approval without disclosing secrets.

## 2. Isolated rehearsal

Run only with a disposable PostgreSQL cluster, synthetic customer/vehicle rows, explicit schema-only object key and the reviewed-source gate. Confirm no production connection strings or live notification destinations are available to the runner. Never run against a real customer-data archive.

Collect: source archive SHA-256 and schema reference; test runner isolation attestation; independently generated primary and recovery age identities; evidence each identity decrypts the **same** encrypted artificial-data archive; exact target cluster ID; source/target row digests; tenant links, FK/uniqueness/check constraints, sequence state, post-restore inserts, cleanup and negative tests. No private keys or personal records in logs.

The existing GitHub Actions synthetic restore is **not** evidence of an executed real-schema rehearsal.

## 3. Separate production release gate

Before considering activation, a separate authorized operator must independently attest the **effective** production reader privileges, including inherited/PUBLIC grants, RLS and actual access to only intended tables/sequences. Separately verify offline custody, rotation/recovery of both age private identities, retention/privacy/incident handling, archive authenticity and recoverability, and the impact on existing full-CRM backup schedules.

Require written owner approval tied to the exact reviewed PR SHA and evidence bundle. Until then: **Draft PR, no merge, no live schedules, no Production database/storage access, no deployment.**

### Offline archive inspection command

For an independently prepared **non-customer** archive, run on the reviewer's isolated workstation (with `pg_restore` available):

```bash
python3 scripts/inspect-schema-only-archive.py /private/path/crm-schema-only-YYYYMMDD-HHMMSS.dump
```

A successful result prints `SCHEMA_ONLY_TOC_PASS`, the byte size and SHA-256. Compare the digest with an independently supplied value, record reviewer sign-off, and separately inspect SQL definitions/comments for sensitive literals. A pass does **not** authorize uploading the archive or setting `CLIENT_BACKUP_SCHEMA_ONLY_SOURCE_REVIEWED=YES` without independent review. Never attach the archive to a public issue or PR.

## Operator execution checklist — 2026-10-26

This checklist is for an independently authorized operator, not a claim that a rehearsal has run.

1. Provision a **new disposable** PostgreSQL cluster outside production and staging; attest its instance identity, isolated network, empty initial state, and absence of production credentials. Never use forwarded localhost ports.
2. Prepare the schema-only custom-format archive from a permitted **non-customer** schema-equivalent source. Record the PostgreSQL major version, migration SHA, operator and UTC time. Do not use a full CRM backup.
3. Independently inspect the archive offline with `python3 scripts/inspect-schema-only-archive.py /private/path/archive.dump`; review SQL definitions and comments for sensitive literals as well. Record reviewer identity, SHA-256 and approved private object key. Do not upload before approval.
4. Only after this review, provide a least-privilege **read-only** private-object credential to the disposable rehearsal runner, pin `CLIENT_BACKUP_SCHEMA_ONLY_OBJECT_KEY` and `CLIENT_BACKUP_SCHEMA_ONLY_SHA256`, and set the documented reviewed-source and synthetic-only gates. No production database URL or live alert destination may be present.
5. Run the existing one-shot `test/backup/schema-rehearsal.py` in the disposable environment. Collect safe stdout markers `SCHEMA_ONLY_RESTORE_OK`, `REAL_SCHEMA_RECOVERY_OK`, `REAL_SCHEMA_SEQUENCE_RECOVERY_OK`, and `REAL_SCHEMA_REHEARSAL_DONE`, plus exit code and immutable runner/cluster identity. Redact credentials, private keys and row data.
6. Independent reviewer verifies the evidence, including both distinct recipient decryptions, tenant/foreign-key constraints, sequence state, source/target digests, post-restore inserts, and cleanup. Any missing marker, nonzero exit, mismatched digest or ambiguous cluster identity is FAIL/NO-GO.
7. Do not substitute this synthetic rehearsal for an authenticated restore of a separately approved genuine encrypted client archive; that is a distinct production release gate requiring privacy and owner authorization.

**Execution status at this checkpoint: NOT RUN — no independently verified schema-only archive or disposable runner attestation was available. Production remains NO-GO.**
