"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
const {createSession,lookupSession,revokeSession}=require("../lib/crm-session-store");
const {newSession,hashSession}=require("../lib/crm-auth");
test("session insert stores hash only, never raw token",async()=>{
 const session=newSession(),calls=[];
 const db={query:async(sql,params)=>{calls.push({sql,params});return {rowCount:1}}};
 await createSession(db,"staff-1",session);
 assert.equal(calls.length,1);
 assert.equal(calls[0].params[1],session.tokenHash);
 assert.equal(JSON.stringify(calls).includes(session.token),false);
});
test("session lookup uses hashed token and rejects invalid token without query",async()=>{
 const token=crypto.randomBytes(32).toString("hex"),calls=[];
 const db={query:async(sql,params)=>{calls.push({sql,params});return {rows:[{id:"staff-1",role:"owner"}]}}};
 assert.equal((await lookupSession(db,token)).id,"staff-1");
 assert.equal(calls[0].params[0],hashSession(token));
 assert.equal(await lookupSession(db,"invalid"),null);
 assert.equal(calls.length,1);
});
test("session revocation is idempotent and avoids querying malformed token",async()=>{
 const token=crypto.randomBytes(32).toString("hex");let calls=0;
 const db={query:async()=>({rowCount:++calls===1?1:0})};
 assert.equal(await revokeSession(db,token),true);
 assert.equal(await revokeSession(db,token),false);
 assert.equal(await revokeSession(db,"invalid"),false);
 assert.equal(calls,2);
});
