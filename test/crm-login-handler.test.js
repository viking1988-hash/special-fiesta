"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { makeLoginHandler } = require("../lib/crm-login-handler");

function response() {
 return { statusCode: 200, status(n) { this.statusCode=n; return this; }, json(v) { this.body=v; return this; } };
}
test("rejects malformed login without querying database", async () => {
 const db = { query() { throw Error("should not query"); } };
 const res = response();
 await makeLoginHandler(db)({ body: { login: "", password: "" }, ip: "192.0.2.10" }, res);
 assert.equal(res.statusCode, 401);
});
test("unknown employee gets generic invalid credentials response", async () => {
 const db = { query: async () => ({ rows: [] }) };
 const res = response();
 await makeLoginHandler(db)({ body: { login: "nobody", password: "correct-horse-battery", }, ip: "192.0.2.11" }, res);
 assert.equal(res.statusCode, 401);
 assert.equal(res.body.error, "invalid_credentials");
});
