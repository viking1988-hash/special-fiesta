"use strict";
const { lookupSession } = require("./crm-session-store");
const { permitted } = require("./crm-role-policy");
function readSessionCookie(req) {
 const raw = String(req.headers?.cookie || "");
 const match = raw.match(/(?:^|;\s*)crm_session=([0-9a-f]{64})(?:;|$)/);
 return match ? match[1] : null;
}
function staffSessionMiddleware(db) {
 return async (req, res, next) => {
  try {
   const user = await lookupSession(db, readSessionCookie(req));
   if (!user) return res.status(401).json({ ok: false, error: "authentication_required" });
   if (!permitted(user.role, req.method, req.path)) return res.status(403).json({ ok: false, error: "forbidden" });
   req.crmStaff = { id: user.id, login: user.login, role: user.role };
   next();
  } catch {
   res.status(503).json({ ok: false, error: "auth_unavailable" });
  }
 };
}
module.exports = { readSessionCookie, staffSessionMiddleware };
