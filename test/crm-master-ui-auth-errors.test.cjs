"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync(require("node:path").join(__dirname,"../public/index.html"),"utf8");
const source=html.match(/let crmPersonalMode=null;[\s\S]*?\nconst CASE_KEY=/)?.[0].replace(/\nconst CASE_KEY=$/,"");
function setup(responses,inputs){
 const calls=[],messages=[],prompts=[...inputs];
 const context={sessionStorage:{removeItem(){},getItem(){return null},setItem(){}},logEvent:m=>messages.push(m),prompt:()=>prompts.shift()??null,fetch:async(url,opts)=>{calls.push({url,opts});const fn=responses[url];if(!fn)throw Error("unexpected request "+url);return fn();}};
 vm.createContext(context);vm.runInContext(source+"\nthis.runAuth=getOpsHeaders;",context);
 return {context,calls,messages};
}
test("expired staff session triggers a fresh login",async()=>{
 const t=setup({
  "/api/auth/status":async()=>({ok:true,json:async()=>({enabled:true})}),
  "/api/auth/me":async()=>({ok:false,status:401}),
  "/api/auth/login":async()=>({ok:true,json:async()=>({ok:true})})
 },["master-test","a-long-password"]);
 assert.equal(JSON.stringify(await t.context.runAuth()),"{}");
 assert.equal(t.calls.at(-1).url,"/api/auth/login");
 assert.equal(t.calls.at(-1).opts.credentials,"same-origin");
 assert.equal(JSON.parse(t.calls.at(-1).opts.body).login,"master-test");
});
test("wrong password fails closed and logs an error",async()=>{
 const t=setup({
  "/api/auth/status":async()=>({ok:true,json:async()=>({enabled:true})}),
  "/api/auth/me":async()=>({ok:false,status:401}),
  "/api/auth/login":async()=>({ok:false,status:401})
 },["master-test","incorrect-password"]);
 assert.equal(await t.context.runAuth(),null);
 assert.match(t.messages.join(" "),/401/);
});
test("cancelled password prompt does not submit credentials",async()=>{
 const t=setup({
  "/api/auth/status":async()=>({ok:true,json:async()=>({enabled:true})}),
  "/api/auth/me":async()=>({ok:false,status:401})
 },["master-test",null]);
 assert.equal(await t.context.runAuth(),null);
 assert.equal(t.calls.some(x=>x.url==="/api/auth/login"),false);
});
