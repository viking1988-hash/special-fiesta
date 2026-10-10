"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { staffSessionMiddleware } = require("../lib/crm-session-auth");
function response(){return {statusCode:200,status(n){this.statusCode=n;return this;},json(v){this.body=v;return this;}};}
function setup(role, rows=1){
 const token=crypto.randomBytes(32).toString("hex");
 const db={query:async(sql,params)=>{
  assert.match(sql,/s\.revoked_at IS NULL/);
  assert.match(sql,/s\.expires_at>NOW\(\)/);
  assert.match(sql,/u\.enabled=TRUE/);
  assert.equal(params[0],crypto.createHash("sha256").update(token).digest("hex"));
  return {rows:rows?[{id:"staff-1",login:"staff",role}]:[]};
 }};
 return {db,headers:{cookie:"crm_session="+token}};
}
test("owner can view dashboard",async()=>{
 const x=setup("owner"),req={headers:x.headers,method:"GET",path:"/dashboard"},res=response();
 let next=false;await staffSessionMiddleware(x.db)(req,res,()=>{next=true;});
 assert.equal(next,true);assert.equal(req.crmStaff.role,"owner");
});
test("master cannot access owner dashboard",async()=>{
 const x=setup("master"),req={headers:x.headers,method:"GET",path:"/dashboard"},res=response();
 let next=false;await staffSessionMiddleware(x.db)(req,res,()=>{next=true;});
 assert.equal(res.statusCode,403);assert.equal(next,false);
});
test("revoked or expired session returns unauthorized",async()=>{
 const x=setup("owner",0),req={headers:x.headers,method:"GET",path:"/dashboard"},res=response();
 await staffSessionMiddleware(x.db)(req,res,()=>{throw Error("should not pass");});
 assert.equal(res.statusCode,401);
});
