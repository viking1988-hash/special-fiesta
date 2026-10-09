"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const throttle=require("../lib/crm-login-throttle");
test("rate limit blocks sixth failed attempt and resets after window",()=>{
 const login="throttle_"+Math.random().toString(36).slice(2),ip="192.0.2.35",t=1000000;
 for(let i=0;i<5;i++){
  assert.equal(throttle.allowed(login,ip,t),true);
  throttle.recordFailure(login,ip,t);
 }
 assert.equal(throttle.allowed(login,ip,t),false);
 assert.equal(throttle.allowed(login,ip,t+15*60*1000),true);
 throttle.clear(login,ip);
});
test("rate limit keys are isolated by IP and login",()=>{
 const login="throttle_"+Math.random().toString(36).slice(2),ip="192.0.2.36",t=2000000;
 for(let i=0;i<5;i++)throttle.recordFailure(login,ip,t);
 assert.equal(throttle.allowed(login,ip,t),false);
 assert.equal(throttle.allowed(login,"192.0.2.37",t),true);
 assert.equal(throttle.allowed(login+"other",ip,t),true);
 throttle.clear(login,ip);
});
