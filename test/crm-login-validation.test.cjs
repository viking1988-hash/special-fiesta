"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {makeLoginHandler}=require("../lib/crm-login-handler");
function response(){
 return {statusCode:200,status(n){this.statusCode=n;return this},json(body){this.body=body;return this}};
}
test("reject invalid login formats without querying the database",async()=>{
 for(const login of ["a","a b","name@example.com","имя","a/b","a".repeat(101),{},42,null]){
  let queries=0;
  const db={query:async()=>{queries++;throw Error("should not query")}};
  const res=response();
  await makeLoginHandler(db)({body:{login,password:"valid-password-123456"},ip:"192.0.2.15"},res);
  assert.equal(res.statusCode,401,String(login));
  assert.equal(res.body.error,"invalid_credentials");
  assert.equal(queries,0);
 }
});
test("normalize uppercase and whitespace before login lookup",async()=>{
 let searched;
 const db={query:async(_sql,params)=>{searched=params[0];return {rows:[]}}};
 const res=response();
 await makeLoginHandler(db)({body:{login:"  OWNER.TEST  ",password:"valid-password-123456"},ip:"192.0.2.16"},res);
 assert.equal(searched,"owner.test");
 assert.equal(res.statusCode,401);
});

test("reject missing or oversized passwords without database access",async()=>{
 for(const password of [undefined,null,12,"short","x".repeat(257)]){
  let queries=0;
  const db={query:async()=>{queries++;throw Error("unexpected query")}};
  const res=response();
  await makeLoginHandler(db)({body:{login:"owner.test",password},ip:"192.0.2.21"},res);
  assert.equal(res.statusCode,401);
  assert.equal(queries,0);
 }
});
test("return service unavailable without leaking database errors",async()=>{
 const db={query:async()=>{throw Error("database-secret-connection-details")}};
 const res=response();
 await makeLoginHandler(db)({body:{login:"owner.test",password:"valid-password-123456"},ip:"192.0.2.22"},res);
 assert.equal(res.statusCode,503);
 assert.equal(res.body.error,"auth_unavailable");
 assert.doesNotMatch(JSON.stringify(res.body),/database-secret/);
});
test("reject missing request body without throwing",async()=>{
 const db={query:async()=>{throw Error("unexpected query")}};
 const res=response();
 await makeLoginHandler(db)({ip:"192.0.2.23"},res);
 assert.equal(res.statusCode,401);
});

test("reject passwords below minimum length without querying database",async()=>{
 for(const password of ["","x".repeat(11)]){
  let queries=0;
  const db={query:async()=>{queries++;throw Error("unexpected query")}};
  const res=response();
  await makeLoginHandler(db)({body:{login:"owner.test",password},ip:"192.0.2.24"},res);
  assert.equal(res.statusCode,401);
  assert.equal(queries,0);
 }
});
