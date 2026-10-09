"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(require("node:path").join(__dirname,"../public/owner.html"),"utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
test("owner UI locks legacy login when auth mode request fails",async()=>{
  assert.ok(script,"owner script is present");
  const elements = Object.fromEntries(["staffLogin","accessKey","authStatus","login","queue","history","total","approved","handed","logout","go"].map(id=>[id,{style:{},disabled:false,textContent:"",placeholder:""}]));
  const context={...elements,sessionStorage:{getItem(){return "legacy-secret"},removeItem(){},setItem(){}},fetch:async()=>{throw Error("auth status unavailable")}};
  vm.createContext(context);
  vm.runInContext(script,context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(elements.login.disabled,true);
  assert.equal(elements.accessKey.disabled,true);
  assert.equal(elements.staffLogin.disabled,true);
  assert.match(elements.authStatus.textContent,/заблокирован/);
  assert.equal(elements.queue.textContent,"Проверка режима доступа недоступна");
});

test("owner UI rejects unsuccessful or malformed auth status",async()=>{
 for(const response of [{ok:false,status:503,json:async()=>({enabled:false})},{ok:true,json:async()=>({})},{ok:true,json:async()=>({enabled:"false"})}]){
  const elements=Object.fromEntries(["staffLogin","accessKey","authStatus","login","queue","history","total","approved","handed","logout","go"].map(id=>[id,{style:{},disabled:false,textContent:"",placeholder:""}]));
  const context={...elements,sessionStorage:{getItem(){return "legacy-secret"},removeItem(){},setItem(){}},fetch:async()=>response};
  vm.createContext(context);vm.runInContext(script,context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(elements.login.disabled,true);
  assert.equal(elements.accessKey.disabled,true);
  assert.match(elements.authStatus.textContent,/заблокирован/);
 }
});
