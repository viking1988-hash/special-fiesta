# Personal CRM auth — controlled rollout

Do not enable CRM_PERSONAL_AUTH_ENABLED until all steps have been validated.

1. Back up PostgreSQL and confirm a working restore path.
2. Deploy tested code to a staging environment with a staging database.
3. Run `node scripts/crm-init-schema.cjs` with DATABASE_URL configured.
4. Provide CRM_OWNER_LOGIN and CRM_OWNER_PASSWORD (at least 16 characters) as temporary protected environment variables; run `node scripts/crm-create-owner.cjs`. Never put passwords in shell history, repository, logs or chat. Remove provisioning credentials immediately.
5. Test login, /api/auth/me, /api/ops owner-only routes, logout, revoked sessions, role restrictions and CSRF rejection on staging.
6. Ensure owner UI supports cookie-based sessions; legacy x-ops-token UI will not work after switching auth on.
7. Enable CRM_PERSONAL_AUTH_ENABLED=true only in a controlled production maintenance window after staging passes.
8. Verify production login and owner operations, and inspect logs without exposing secrets.
9. Roll back by setting CRM_PERSONAL_AUTH_ENABLED=false; legacy OPS_ACCESS_TOKEN and MASTER_ACCESS_TOKEN must remain configured and protected during transition.

Caution: the login throttle is per-process memory and is not distributed across instances. Do not rely on it alone for production abuse protection.

10. Confirm the staging DATABASE_URL points to the intended staging database before provisioning; never run bootstrap against production during tests.
11. Check whether the database provider requires TLS and set connection-string SSL parameters accordingly. Do not bypass certificate verification as a workaround.
12. After provisioning, confirm a second run with the same login fails without changing the existing password or role.
