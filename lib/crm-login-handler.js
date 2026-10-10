"use strict";
const auth = require("./crm-auth");
const sessions = require("./crm-session-store");
const throttle = require("./crm-login-throttle-db");

function makeLoginHandler(db) {
 return async (req, res) => {
  const login = typeof req.body?.login === "string" ? req.body.login.trim().toLowerCase() : "";
  const password = req.body?.password;
  const ip = req.ip || "unknown";
  if (!/^[a-z0-9._-]{3,100}$/.test(login) || typeof password !== "string" || password.length < 12 || password.length > 256) {
   return res.status(401).json({ ok: false, error: "invalid_credentials" });
  }
  try {
   if (!await throttle.allowed(db, login, ip)) return res.status(429).json({ ok: false, error: "too_many_attempts" });
   const found = await db.query(
    "SELECT id, login, role, password_salt, password_hash FROM crm_staff WHERE login=$1 AND enabled=TRUE LIMIT 1",
    [login]
   );
   const user = found.rows[0];
   if (!user || !auth.verifyPassword(password, user.password_salt, user.password_hash)) {
    await throttle.recordFailure(db, login, ip);
    return res.status(401).json({ ok: false, error: "invalid_credentials" });
   }
   const session = auth.newSession();
   await sessions.createSession(db, user.id, session);
   await throttle.clear(db, login, ip);
   res.cookie("crm_session", session.token, auth.cookieOptions());
   return res.json({ ok: true, role: user.role, login: user.login });
  } catch {
   return res.status(503).json({ ok: false, error: "auth_unavailable" });
  }
 };
}
module.exports = { makeLoginHandler };
