"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync(require("node:path").join(__dirname,"../public/owner.html"),"utf8");
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
function harness(logoutResponse){
 const ids=["staffLogin","accessKey","authStatus","login","logout","queue","history","total","approved","handed","go","q"];
 const els=Object.fromEntries(ids.map(id=>[id,{style:{},disabled:false,value:"",textContent:"",placeholder:""}]));
 const calls=[];
 const ctx={...els,sessionStorage:{getItem(){return null},removeItem(){},setItem(){}},fetch:async(url,options)=>{
  calls.push({url,options});
  if(url==="/api/auth/status")return {ok:true,json:async()=>({enabled:true})};
  if(url==="/api/ops/dashboard")return {ok:false,status:401};
  if(url==="/api/auth/logout")return logoutResponse();
  throw Error("unexpected "+url);
 }};
 vm.createContext(ctx);vm.runInContext(script,ctx);
 return {els,calls,ctx};
}
test("owner logout does not report success if revocation fails",async()=>{
 for(const response of [async()=>({ok:false,status:503}),async()=>{throw Error("network")}]) {
  const t=harness(response);
  await new Promise(resolve=>setImmediate(resolve));
  await t.els.logout.onclick();
  assert.doesNotMatch(t.els.authStatus.textContent,/Вы вышли/);
  assert.match(t.els.authStatus.textContent,/сесси|Сервер/);
  assert.equal(t.calls.filter(x=>x.url==="/api/auth/logout").length,1);
 }
});
test("owner logout reports success after server revocation",async()=>{
 const t=harness(async()=>({ok:true,status:200}));
 await new Promise(resolve=>setImmediate(resolve));
 await t.els.logout.onclick();
 assert.match(t.els.authStatus.textContent,/Вы вышли/);
 assert.equal(t.els.queue.textContent,"Нет доступа");
});
