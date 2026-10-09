"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
const {makeLoginHandler}=require("../lib/crm-login-handler");
function response(){
 return {statusCode:200,status(n){this.statusCode=n;return this},cookie(n,v,o){this.cookieName=n;this.cookieValue=v;this.cookieOptions=o;return this},json(v){this.body=v;return this}};
}
test("successful owner login creates session and sets secure cookie",async()=>{
 const login="owner.test",password="strong-owner-password-123";
 const salt=crypto.randomBytes(16).toString("hex");
 const hash=crypto.scryptSync(password,salt,64).toString("hex");
 const queries=[];
 const db={query:async(sql,params)=>{
  queries.push({sql,params});
  if(sql.includes("SELECT id, login"))return {rows:[{id:"owner-1",login,role:"owner",password_salt:salt,password_hash:hash}]};
  return {rowCount:1};
 }};
 const res=response();
 await makeLoginHandler(db)({body:{login,password},ip:"192.0.2.180"},res);
 assert.equal(res.statusCode,200);
 assert.equal(res.body.ok,true);
 assert.equal(res.body.role,"owner");
 assert.equal(res.cookieName,"crm_session");
 assert.match(res.cookieValue,/^[0-9a-f]{64}$/);
 assert.equal(res.cookieOptions.secure,true);
 assert.equal(res.cookieOptions.httpOnly,true);
 assert.equal(queries.length,2);
 assert.equal(queries[1].params[1],crypto.createHash("sha256").update(res.cookieValue).digest("hex"));
});
test("failed password does not create session or cookie",async()=>{
 const login="owner.test",salt=crypto.randomBytes(16).toString("hex");
 const hash=crypto.scryptSync("correct-password-123",salt,64).toString("hex");
 let queries=0;
 const db={query:async()=>{queries++;return {rows:[{id:"owner-2",login,role:"owner",password_salt:salt,password_hash:hash}]}}};
 const res=response();
 await makeLoginHandler(db)({body:{login,password:"wrong-password-123"},ip:"192.0.2.181"},res);
 assert.equal(res.statusCode,401);
 assert.equal(res.body.error,"invalid_credentials");
 assert.equal(res.cookieName,undefined);
 assert.equal(queries,1);
});
test("session storage failure does not issue a cookie",async()=>{
 const login="owner.test",password="strong-owner-password-456",salt=crypto.randomBytes(16).toString("hex");
 const hash=crypto.scryptSync(password,salt,64).toString("hex");
 const db={query:async(sql)=>{
  if(sql.includes("SELECT id, login"))return {rows:[{id:"owner-3",login,role:"owner",password_salt:salt,password_hash:hash}]};
  throw Error("private session storage failure");
 }};
 const res=response();
 await makeLoginHandler(db)({body:{login,password},ip:"192.0.2.182"},res);
 assert.equal(res.statusCode,503);
 assert.equal(res.cookieName,undefined);
 assert.doesNotMatch(JSON.stringify(res.body),/private session/);
});
