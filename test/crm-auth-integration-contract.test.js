"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const server = fs.readFileSync(path.join(__dirname,"../server.js"),"utf8");
const owner = fs.readFileSync(path.join(__dirname,"../public/owner.html"),"utf8");
test("staff login is gated by rollout flag",()=>{
 assert.match(server,/app\.post\("\/api\/auth\/login"/);
 assert.match(server,/if\(!personalAuthEnabled\(\)\)return res\.sendStatus\(404\)/);
});
test("ops middleware uses session auth when flag enabled",()=>{
 assert.match(server,/app\.use\("\/api\/ops"/);
 assert.match(server,/require\("\.\/lib\/crm-csrf"\)/);
 assert.match(server,/require\("\.\/lib\/crm-session-auth"\)/);
});
test("owner UI uses same-origin credentials and no local password persistence",()=>{
 assert.match(owner,/credentials:"same-origin"/);
 assert.match(owner,/sessionStorage\.removeItem\("avtohirurg_ops_token"\)/);
 assert.doesNotMatch(owner,/sessionStorage\.setItem\("crm_password"/);
});
