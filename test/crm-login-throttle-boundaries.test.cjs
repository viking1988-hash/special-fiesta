"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const throttle = require("../lib/crm-login-throttle");

test("failed attempts for one login and IP do not lock another operator", () => {
 const now = Date.now(), ip = "192.0.2.41";
 const blocked = "blocked-" + now, other = "other-" + now;
 for (let i = 0; i < 5; i++) throttle.recordFailure(blocked, ip, now);
 assert.equal(throttle.allowed(blocked, ip, now), false);
 assert.equal(throttle.allowed(other, ip, now), true);
 assert.equal(throttle.allowed(blocked, "192.0.2.42", now), true);
});

test("lockout lasts for the entire fifteen-minute window", () => {
 const now = Date.now(), login = "boundary-" + now, ip = "192.0.2.43";
 for (let i = 0; i < 5; i++) throttle.recordFailure(login, ip, now);
 assert.equal(throttle.allowed(login, ip, now + 15 * 60 * 1000 - 1), false);
 assert.equal(throttle.allowed(login, ip, now + 15 * 60 * 1000), true);
});

test("login comparison is case insensitive for throttling", () => {
 const now = Date.now(), login = "Case-" + now, ip = "192.0.2.44";
 for (let i = 0; i < 5; i++) throttle.recordFailure(login, ip, now);
 assert.equal(throttle.allowed(login.toLowerCase(), ip, now), false);
});
