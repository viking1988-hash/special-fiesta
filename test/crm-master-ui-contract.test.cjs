"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const html=fs.readFileSync(path.join(__dirname,"../public/index.html"),"utf8");
test("master UI checks feature flag before selecting authentication",()=>{
 assert.match(html,/fetch\("\/api\/auth\/status"/);
 assert.match(html,/crmPersonalMode=!!j\.enabled/);
});
test("master UI recognizes role returned by staff session endpoint",()=>{
 assert.match(html,/fetch\("\/api\/auth\/me"/);
 assert.match(html,/j\.user\?\.role==="master"/);
 assert.match(html,/j\.user\?\.role==="owner"/);
});
test("master UI logs in with same-origin cookie credentials",()=>{
 assert.match(html,/fetch\("\/api\/auth\/login"/);
 assert.match(html,/credentials:"same-origin"/);
});
test("master UI retains legacy access only in disabled personal mode",()=>{
 assert.match(html,/sessionStorage\.removeItem\("avtohirurg_master_token"\)/);
 assert.match(html,/return token\?\{"x-ops-token":token\}:null/);
 assert.match(html,/const auth=await getOpsHeaders\(\)/);
});
