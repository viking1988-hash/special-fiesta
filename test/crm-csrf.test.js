"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { requireTrustedOrigin } = require("../lib/crm-csrf");
function request(method, origin) {
 const headers={host:"crm.example.test","x-forwarded-proto":"https",origin};
 return {method,get:(name)=>headers[name],secure:false};
}
function response() {return {statusCode:200,status(n){this.statusCode=n;return this;},json(v){this.body=v;return this;}};}
test("safe GET is allowed without Origin",()=>{
 let called=false;
 requireTrustedOrigin(request("GET"),response(),()=>{called=true;});
 assert.equal(called,true);
});
test("rejects mutation without Origin",()=>{
 let called=false;const res=response();
 requireTrustedOrigin(request("POST"),res,()=>{called=true;});
 assert.equal(res.statusCode,403);assert.equal(called,false);
});
test("allows same-origin mutation",()=>{
 let called=false;
 requireTrustedOrigin(request("POST","https://crm.example.test"),response(),()=>{called=true;});
 assert.equal(called,true);
});
test("rejects foreign Origin",()=>{
 const res=response();
 requireTrustedOrigin(request("DELETE","https://evil.example.test"),res,()=>{});
 assert.equal(res.statusCode,403);
});
