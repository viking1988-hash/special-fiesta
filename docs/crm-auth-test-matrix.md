# CRM access regression matrix

| Scenario | Expected |
|---|---|
| No credential -> GET /api/ops/dashboard | 401 |
| Master -> GET /api/ops/dashboard | 403 |
| Owner -> GET /api/ops/dashboard | 200 |
| Master -> POST /api/ops/drafts | Allowed with valid payload |
| Master -> GET /api/ops/drafts/:id | Allowed for authorized draft |
| Master -> GET /api/ops/vehicle | 403 |
| Disabled master -> draft endpoint | 401 |
| Revoked session -> any protected endpoint | 401 |
| Expired session -> any protected endpoint | 401 |
| Malformed session cookie | 401, no crash |
| Invalid login repeated | Rate limit, no account enumeration |
| Logout -> reuse cookie | 401 |
| Owner session -> master workflow | Defined explicitly before release |
| Existing legacy keys while flag disabled | No behavior change |

The new cookie-authenticated mode must not be enabled before these tests are automated and passing.
