"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const throttle = require("../lib/crm-login-throttle");
test("locks after five failures and resets after window", () => {
 const login = "test-" + Date.now(), ip = "192.0.2.1", start = 1000;
 for (let i = 0; i < 5; i++) {
  assert.equal(throttle.allowed(login, ip, start), true);
  throttle.recordFailure(login, ip, start);
 }
 assert.equal(throttle.allowed(login, ip, start), false);
 assert.equal(throttle.allowed(login, ip, start + 900001), true);
});
test("successful login can clear attempts", () => {
 const login = "clear-" + Date.now(), ip = "192.0.2.2";
 for (let i = 0; i < 5; i++) throttle.recordFailure(login, ip);
 assert.equal(throttle.allowed(login, ip), false);
 throttle.clear(login, ip);
 assert.equal(throttle.allowed(login, ip), true);
});
