"use strict";
const { hashSession } = require("./crm-auth");
async function createSession(db, staffId, session) {
  if (!db || !staffId || !session || !session.tokenHash) throw Error("invalid_session");
  await db.query(
    "INSERT INTO crm_staff_sessions(id,staff_id,token_hash,expires_at) VALUES(gen_random_uuid(),$1,$2,NOW()+INTERVAL '8 hours')",
    [staffId, session.tokenHash]
  );
}
async function lookupSession(db, token) {
  const hash = hashSession(token);
  if (!db || !hash) return null;
  const result = await db.query(
    "SELECT u.id,u.login,u.role FROM crm_staff_sessions s JOIN crm_staff u ON u.id=s.staff_id WHERE s.token_hash=$1 AND s.revoked_at IS NULL AND s.expires_at>NOW() AND u.enabled=TRUE LIMIT 1",
    [hash]
  );
  return result.rows[0] || null;
}
async function revokeSession(db, token) {
  const hash = hashSession(token);
  if (!db || !hash) return false;
  const result = await db.query(
    "UPDATE crm_staff_sessions SET revoked_at=NOW() WHERE token_hash=$1 AND revoked_at IS NULL",
    [hash]
  );
  return result.rowCount > 0;
}
module.exports = { createSession, lookupSession, revokeSession };
