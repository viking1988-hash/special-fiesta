"use strict";
const crypto = require("node:crypto");

function verifyPassword(password, salt, expectedHex) {
  if (typeof password !== "string" || typeof salt !== "string" ||
      typeof expectedHex !== "string" || !/^[0-9a-f]{128}$/i.test(expectedHex)) return false;
  if (password.length > 256 || salt.length > 256) return false;
  const expected = Buffer.from(expectedHex, "hex");
  const actual = crypto.scryptSync(password, salt, expected.length);
  return crypto.timingSafeEqual(actual, expected);
}

function newSession() {
  const token = crypto.randomBytes(32).toString("hex");
  return { token, tokenHash: crypto.createHash("sha256").update(token).digest("hex") };
}

function hashSession(token) {
  if (typeof token !== "string" || !/^[0-9a-f]{64}$/.test(token)) return null;
  return crypto.createHash("sha256").update(token).digest("hex");
}

function cookieOptions() {
  return { httpOnly: true, secure: true, sameSite: "strict", path: "/api", maxAge: 8 * 60 * 60 * 1000 };
}

module.exports = { verifyPassword, newSession, hashSession, cookieOptions };
