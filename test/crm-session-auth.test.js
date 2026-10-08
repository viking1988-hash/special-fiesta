"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { readSessionCookie, staffSessionMiddleware } = require("../lib/crm-session-auth");
test("extracts only correctly formatted session cookies", () => {
 const token = "a".repeat(64);
 assert.equal(readSessionCookie({headers:{cookie:"foo=bar; crm_session="+token}}), token);
 assert.equal(readSessionCookie({headers:{cookie:"crm_session=invalid"}}), null);
 assert.equal(readSessionCookie({headers:{}}), null);
});
test("rejects missing session before role check", async () => {
 const db = { query() { throw Error("must not query"); } };
 const req = { headers:{}, method:"GET", path:"/dashboard" };
 const res = { statusCode:200, status(n){this.statusCode=n;return this;}, json(v){this.body=v;return this;} };
 let nextCalled = false;
 await staffSessionMiddleware(db)(req,res,()=>{nextCalled=true;});
 assert.equal(res.statusCode,401);
 assert.equal(nextCalled,false);
});
