"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { makeLoginHandler } = require("../lib/crm-login-handler");
test("valid employee receives a session cookie backed by a hashed DB token", async () => {
 const salt = crypto.randomBytes(16).toString("hex");
 const password = "secure-test-password-12345";
 const password_hash = crypto.scryptSync(password,salt,64).toString("hex");
 const calls=[];
 const db={query:async(sql,params)=>{
  calls.push({sql,params});
  if(sql.includes("FROM crm_login_attempts"))return {rows:[]};
  if(sql.includes("FROM crm_staff WHERE"))return {rows:[{id:"00000000-0000-4000-8000-000000000001",login:"owner",role:"owner",password_salt:salt,password_hash}]};
  if(sql.startsWith("INSERT")||sql.startsWith("DELETE"))return {rowCount:1};
  throw Error("unexpected SQL");
 }};
 const res={statusCode:200,status(n){this.statusCode=n;return this;},cookie(name,token,options){this.cookieData={name,token,options};return this;},json(body){this.body=body;return this;}};
 await makeLoginHandler(db)({body:{login:"owner",password},ip:"192.0.2.150"},res);
 assert.equal(res.statusCode,200);
 assert.equal(res.body.role,"owner");
 assert.equal(res.cookieData.name,"crm_session");
 assert.equal(res.cookieData.options.httpOnly,true);
 assert.equal(res.cookieData.options.secure,true);
 assert.equal(calls.filter(x=>x.sql.includes("INSERT INTO crm_staff_sessions")).length,1);
 assert.notEqual(calls.find(x=>x.sql.includes("INSERT INTO crm_staff_sessions")).params[1],res.cookieData.token);
 assert.equal(calls.find(x=>x.sql.includes("INSERT INTO crm_staff_sessions")).params[1],crypto.createHash("sha256").update(res.cookieData.token).digest("hex"));
});
