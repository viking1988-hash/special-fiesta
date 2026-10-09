"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
const {verifyPassword,newSession,hashSession,cookieOptions}=require("../lib/crm-auth");
test("password verification accepts correct secret and rejects wrong secret",()=>{
 const salt=crypto.randomBytes(16).toString("hex"),password="strong-owner-password-123";
 const hash=crypto.scryptSync(password,salt,64).toString("hex");
 assert.equal(verifyPassword(password,salt,hash),true);
 assert.equal(verifyPassword("wrong-password",salt,hash),false);
});
test("password verification rejects malformed hashes and salts",()=>{
 for(const args of [[null,"salt","a".repeat(128)],["secret","","a".repeat(128)],["secret","salt","invalid"],["secret","salt","a".repeat(127)],["secret","salt","a".repeat(129)],["x".repeat(257),"salt","a".repeat(128)]]){
  assert.equal(verifyPassword(...args),false);
 }
});
test("sessions use distinct 256-bit tokens and hashed storage",()=>{
 const a=newSession(),b=newSession();
 assert.match(a.token,/^[0-9a-f]{64}$/);
 assert.match(a.tokenHash,/^[0-9a-f]{64}$/);
 assert.notEqual(a.token,b.token);
 assert.notEqual(a.token,a.tokenHash);
 assert.equal(hashSession(a.token),a.tokenHash);
 for(const invalid of ["","abc","A".repeat(64),"z".repeat(64),"a".repeat(65),null]){
  assert.equal(hashSession(invalid),null);
 }
});
test("session cookies are secure, HTTP-only and scoped to API",()=>{
 const opts=cookieOptions();
 assert.equal(opts.httpOnly,true);
 assert.equal(opts.secure,true);
 assert.equal(opts.sameSite,"strict");
 assert.equal(opts.path,"/api");
 assert.equal(opts.maxAge,28800000);
});
