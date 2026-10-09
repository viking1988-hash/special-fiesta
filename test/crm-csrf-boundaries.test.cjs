"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {requireTrustedOrigin}=require("../lib/crm-csrf");
function invoke(method,origin,host="crm.example.test",secure=true){
 const req={method,secure,get:key=>key==="origin"?origin:key==="host"?host:undefined};
 const res={statusCode:200,status(n){this.statusCode=n;return this},json(x){this.body=x;return this}};
 let passed=false;requireTrustedOrigin(req,res,()=>{passed=true});
 return {res,passed};
}
test("safe methods pass without Origin",()=>{
 for(const method of ["GET","HEAD","OPTIONS"]){
  const x=invoke(method,undefined);assert.equal(x.passed,true);
 }
});
test("unsafe methods reject absent, foreign and deceptive origins",()=>{
 for(const method of ["POST","PUT","PATCH","DELETE"]){
  for(const origin of [undefined,"https://evil.test","https://crm.example.test.evil.test","http://crm.example.test","null"]){
   const x=invoke(method,origin);
   assert.equal(x.passed,false,method+" "+origin);
   assert.equal(x.res.statusCode,403);
   assert.equal(x.res.body.error,"untrusted_origin");
  }
 }
});
test("unsafe methods accept exact same-origin requests",()=>{
 for(const method of ["POST","PUT","PATCH","DELETE"]){
  assert.equal(invoke(method,"https://crm.example.test").passed,true);
 }
});
