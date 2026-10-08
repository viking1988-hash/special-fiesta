"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { newSession } = require("../lib/crm-auth");
const { createSession, lookupSession, revokeSession } = require("../lib/crm-session-store");

test("create session stores hash rather than raw token", async () => {
  const session = newSession();
  const db = { query: async (sql, params) => {
    assert.match(sql, /INSERT INTO crm_staff_sessions/);
    assert.equal(params[1], session.tokenHash);
    assert.notEqual(params[1], session.token);
    return { rowCount: 1 };
  }};
  await createSession(db, "staff-id", session);
});
test("lookup rejects malformed token without DB query", async () => {
  const db = { query: () => { throw Error("unexpected query"); } };
  assert.equal(await lookupSession(db, "bad"), null);
});
test("revocation updates by hash", async () => {
  const session = newSession();
  const db = { query: async (sql, params) => {
    assert.match(sql, /revoked_at=NOW\(\)/);
    assert.equal(params[0], session.tokenHash);
    return { rowCount: 1 };
  }};
  assert.equal(await revokeSession(db, session.token), true);
});
