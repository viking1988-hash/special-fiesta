"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {requiredRole,permitted}=require("../lib/crm-role-policy");
test("only master draft operations are allowed to master role",()=>{
 const allowed=[["POST","/drafts"],["GET","/drafts/123"],["GET","/drafts/abc-123"]];
 for(const [method,path] of allowed){
  assert.equal(requiredRole(method,path),"master");
  assert.equal(permitted("master",method,path),true);
  assert.equal(permitted("owner",method,path),true);
 }
});
test("master cannot access owner dashboard or write routes",()=>{
 for(const [method,path] of [["GET","/dashboard"],["GET","/vehicle"],["POST","/dashboard"],["DELETE","/drafts/123"],["PATCH","/drafts/123"],["GET","/drafts"],["POST","/staff"],["GET","/drafts/123/history"]]){
  assert.equal(permitted("master",method,path),false,method+" "+path);
  assert.equal(permitted("owner",method,path),true);
 }
});
test("unknown roles never receive permissions",()=>{
 for(const role of ["",null,undefined,"admin","MASTER","staff",{}]){
  assert.equal(permitted(role,"GET","/drafts/123"),false);
  assert.equal(permitted(role,"GET","/dashboard"),false);
 }
});
