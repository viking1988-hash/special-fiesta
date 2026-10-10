"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {readSessionCookie,staffSessionMiddleware}=require("../lib/crm-session-auth");
function response(){
 return {statusCode:200,status(n){this.statusCode=n;return this},json(v){this.body=v;return this}};
}
test("session cookie parser accepts only full lowercase 64-digit hex tokens",()=>{
 const good="a".repeat(64);
 assert.equal(readSessionCookie({headers:{cookie:"x=1; crm_session="+good+"; y=2"}}),good);
 for(const value of ["","abc","g".repeat(64),"A".repeat(64),"a".repeat(65)]){
  assert.equal(readSessionCookie({headers:{cookie:"crm_session="+value}}),null);
 }
 assert.equal(readSessionCookie({headers:{}}),null);
});
test("staff session middleware rejects missing session",async()=>{
 const res=response();let nextCalled=false;
 await staffSessionMiddleware({query:async()=>{throw Error("unexpected database call")}})({headers:{},method:"GET",path:"/dashboard"},res,()=>{nextCalled=true});
 assert.equal(res.statusCode,401);assert.equal(nextCalled,false);
});
test("staff session middleware enforces master vs owner permissions",async()=>{
 const token="b".repeat(64);
 for(const role of ["master","owner"]){
  const db={query:async()=>({rows:[{id:"staff-id",login:"test",role}]})};
  const req={headers:{cookie:"crm_session="+token},method:"GET",path:"/dashboard"};
  const res=response();let nextCalled=false;
  await staffSessionMiddleware(db)(req,res,()=>{nextCalled=true});
  assert.equal(nextCalled,role==="owner");
  if(role==="master")assert.equal(res.statusCode,403);
  else assert.equal(req.crmStaff.role,"owner");
 }
});
test("staff session middleware returns generic error on database outage",async()=>{
 const db={query:async()=>{throw Error("private database host")}};
 const res=response();
 await staffSessionMiddleware(db)({headers:{cookie:"crm_session="+"c".repeat(64)},method:"GET",path:"/dashboard"},res,()=>{});
 assert.equal(res.statusCode,503);
 assert.equal(res.body.error,"auth_unavailable");
 assert.doesNotMatch(JSON.stringify(res.body),/private database host/);
});
