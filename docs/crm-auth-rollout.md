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
