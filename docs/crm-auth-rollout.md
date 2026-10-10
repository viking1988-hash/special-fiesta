# CRM personal authentication: deployment plan

## Batch A — isolated development
- Keep `CRM_PERSONAL_AUTH_ENABLED` disabled in production.
- Implement migrations in a dedicated script, not on each request.
- Create owner bootstrap via a one-time administrative command; never expose a public registration endpoint.
- Store password verifiers using scrypt with unique salts.

## Batch B — security and access tests
- Check session cookie attributes, session expiry, revocation, disabled users and concurrent sessions.
- Check 401 for unauthenticated calls and 403 for a master accessing owner-only routes.
- Add rate limiting and CSRF protection for all mutating cookie-authenticated routes.
- Verify SQL parameters are bound and errors do not leak sensitive data.

## Batch C — controlled release
- Back up PostgreSQL and record current Railway deployment commit.
- Run migration and bootstrap owner before enabling the flag.
- Enable on a staging environment first and perform authenticated smoke tests.
- Only then enable in production; preserve legacy access during the transition.
- Roll back the flag and deployment if login, role checks or draft workflows fail.

## Exit criteria
Do not merge or deploy merely because a PR exists. Require reviewed code, passing automated tests, backup, and manual production smoke checks.

## Evidence collected 2026-10-09
- Automated checks passed on the feature branch: CRM auth, PostgreSQL integration, and Jarvis runtime.
- Railway `Avtohirurg-CRM` has a production environment only. Staging has not been provisioned.
- Backup log: `backup_ok file=crm-20261009-023155.dump bytes=76116`.
- Backup checker: `BACKUP_CHECK_OK`, PostgreSQL dump signature verified.
- Restore rehearsal: `RESTORE_TEST_OK tables=25 archive=crm-20261009-023155.dump`.
- Yandex mirror: `yandex_mirror_ok` for the same archive.

## Remaining release gates
1. Create isolated staging with its own database and credentials. Never use the production database URL.
2. Disable outgoing customer notifications, SMS, Telegram messages, and production webhooks in staging.
3. Run schema setup and one-time owner bootstrap against staging only.
4. Verify login, lockout, cookies, session revocation, owner/master access, CSRF, and legacy access through HTTP smoke tests.
5. Record rollback results and obtain explicit approval before changing production.
