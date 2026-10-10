"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const crypto = require("node:crypto");
const auth = require("../lib/crm-auth");

test("scrypt verification accepts correct password and rejects wrong one", () => {
  const salt = crypto.randomBytes(16).toString("hex");
  const hash = crypto.scryptSync("correct horse battery staple", salt, 64).toString("hex");
  assert.equal(auth.verifyPassword("correct horse battery staple", salt, hash), true);
  assert.equal(auth.verifyPassword("wrong password", salt, hash), false);
  assert.equal(auth.verifyPassword("correct horse battery staple", salt, "bad"), false);
});
test("session tokens are random and hashes cannot be used as tokens", () => {
  const a = auth.newSession(), b = auth.newSession();
  assert.notEqual(a.token, b.token);
  assert.equal(auth.hashSession(a.token), a.tokenHash);
  assert.equal(auth.hashSession("invalid"), null);
});
test("session cookie is httpOnly, secure and strict", () => {
  const c = auth.cookieOptions();
  assert.equal(c.httpOnly, true);
  assert.equal(c.secure, true);
  assert.equal(c.sameSite, "strict");
  assert.equal(c.maxAge, 28800000);
});
