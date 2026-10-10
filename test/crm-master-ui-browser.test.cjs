"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync(require("node:path").join(__dirname,"../public/index.html"),"utf8");
const source=html.match(/let crmPersonalMode=null;[\s\S]*?\nconst CASE_KEY=/)?.[0].replace(/\nconst CASE_KEY=$/,"");
test("master UI reuses valid staff session without asking for credentials",async()=>{
 assert.ok(source,"master auth helper found");
 const requests=[];
 const storage={removeItem(){},getItem(){return null},setItem(){}};
 const context={sessionStorage:storage,logEvent(){throw Error("unexpected log")},prompt(){throw Error("unexpected prompt")},fetch:async(url)=>{
 requests.push(url);
 if(url==="/api/auth/status")return {ok:true,json:async()=>({enabled:true})};
 if(url==="/api/auth/me")return {ok:true,json:async()=>({user:{role:"master"}})};
 throw Error("unexpected request");
 }};
 vm.createContext(context);
 vm.runInContext(source+"\nthis.runAuth=getOpsHeaders;",context);
 const headers=await context.runAuth();
 assert.equal(JSON.stringify(headers),"{}");
 assert.deepEqual(requests,["/api/auth/status","/api/auth/me"]);
});
test("master UI retains legacy token while feature is disabled",async()=>{
 const context={sessionStorage:{getItem(){return "legacy-test-token"},setItem(){},removeItem(){}},logEvent(){},prompt(){throw Error("unexpected prompt")},fetch:async()=>({ok:true,json:async()=>({enabled:false})})};
 vm.createContext(context);
 vm.runInContext(source+"\nthis.runAuth=getOpsHeaders;",context);
 assert.equal(context.runAuth instanceof Function,false);
 const headers=await context.runAuth();
 assert.equal(headers["x-ops-token"],"legacy-test-token");
});
