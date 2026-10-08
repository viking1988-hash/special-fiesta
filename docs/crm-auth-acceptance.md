# CRM staff authentication — acceptance criteria

The feature flag remains disabled until all criteria pass.

- Database migration creates staff and session tables without altering existing orders.
- Passwords use unique salts and a memory-hard hash; plaintext is never logged.
- Login requests are rate-limited and return a generic failure for unknown accounts.
- Session cookies are HttpOnly, Secure and SameSite; sessions expire and can be revoked.
- Owner can access management routes; master can access only allowed draft operations.
- Disabled employees immediately lose access, including existing sessions.
- Logout invalidates the session server-side.
- Unauthenticated calls fail closed; malformed cookies do not crash the service.
- Cross-site requests cannot perform state-changing operations.
- No credentials appear in repository, deployment logs or client JavaScript.
- Existing legacy login works during migration; rollback is documented and tested.
- Tests cover 401, 403, 200, expiration, revocation, and disabled accounts.
- Production rollout requires a backup and explicit verification.
