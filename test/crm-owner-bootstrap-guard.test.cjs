"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const script=fs.readFileSync(path.join(__dirname,"../scripts/crm-create-owner.cjs"),"utf8");
test("owner provisioning requires explicit confirmation before DB pool construction",()=>{
 const gate=script.indexOf('process.env.CRM_OWNER_BOOTSTRAP_CONFIRM !== "YES"');
 const pool=script.indexOf("new Pool(");
 assert.ok(gate>0,"confirmation gate exists");
 assert.ok(pool>gate,"gate precedes DB connection");
});
test("owner provisioning never overwrites existing login credentials",()=>{
 assert.match(script,/ON CONFLICT \(login\) DO NOTHING/);
 assert.doesNotMatch(script,/ON CONFLICT \(login\) DO UPDATE/);
});
test("owner provisioning stores a salted scrypt hash rather than plaintext",()=>{
 assert.match(script,/crypto\.randomBytes\(32\)/);
 assert.match(script,/crypto\.scryptSync\(password,salt,64\)/);
 assert.match(script,/password_salt,password_hash/);
 assert.doesNotMatch(script,/console\.log\(password\)/);
});
