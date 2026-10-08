"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { requiredRole, permitted } = require("../lib/crm-role-policy");

test("only exact draft routes grant master access", () => {
  assert.equal(requiredRole("POST", "/drafts"), "master");
  assert.equal(requiredRole("GET", "/drafts/123"), "master");
  assert.equal(requiredRole("GET", "/drafts"), "owner");
  assert.equal(requiredRole("DELETE", "/drafts/123"), "owner");
  assert.equal(requiredRole("GET", "/drafts/123/other"), "owner");
  assert.equal(requiredRole("GET", "/dashboard"), "owner");
});
test("owner can use CRM while master cannot access management routes", () => {
  assert.equal(permitted("owner", "GET", "/dashboard"), true);
  assert.equal(permitted("master", "POST", "/drafts"), true);
  assert.equal(permitted("master", "GET", "/vehicle"), false);
  assert.equal(permitted("disabled", "GET", "/drafts/123"), false);
});
