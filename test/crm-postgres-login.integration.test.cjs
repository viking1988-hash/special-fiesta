"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { Pool } = require("pg");
const { makeLoginHandler } = require("../lib/crm-login-handler");
const { lookupSession, revokeSession } = require("../lib/crm-session-store");
test("staff login and logout persist correctly in PostgreSQL",{skip:!process.env.CRM_TEST_DATABASE_URL},async()=>{
 const db=new Pool({connectionString:process.env.CRM_TEST_DATABASE_URL,ssl:false,max:1});
 const id=crypto.randomUUID(), login="login_"+crypto.randomBytes(8).toString("hex");
 const salt=crypto.randomBytes(16).toString("hex"),password="integration-password-12345";
 const hash=crypto.scryptSync(password,salt,64).toString("hex");
 try {
  await db.query(`CREATE TABLE IF NOT EXISTS crm_staff (
   id UUID PRIMARY KEY,login TEXT NOT NULL UNIQUE,password_salt TEXT NOT NULL,
   password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK (role IN ('owner','master')),
   enabled BOOLEAN NOT NULL DEFAULT TRUE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await db.query(`CREATE TABLE IF NOT EXISTS crm_staff_sessions (
   id UUID PRIMARY KEY,staff_id UUID NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
   token_hash TEXT NOT NULL UNIQUE,expires_at TIMESTAMPTZ NOT NULL,
   revoked_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await db.query(`CREATE TABLE IF NOT EXISTS crm_login_attempts (key_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL, window_start TIMESTAMPTZ NOT NULL)`);
  await db.query("INSERT INTO crm_staff(id,login,password_salt,password_hash,role) VALUES($1,$2,$3,$4,'owner')",[id,login,salt,hash]);
  const res={statusCode:200,status(n){this.statusCode=n;return this;},cookie(name,token,options){this.sessionToken=token;return this;},json(v){this.body=v;return this;}};
  await makeLoginHandler(db)({body:{login,password},ip:"192.0.2.220"},res);
  assert.equal(res.statusCode,200);
  assert.equal((await lookupSession(db,res.sessionToken)).id,id);
  assert.equal(await revokeSession(db,res.sessionToken),true);
  assert.equal(await lookupSession(db,res.sessionToken),null);
 }finally{await db.query("DELETE FROM crm_staff WHERE id=$1",[id]).catch(()=>{});await db.end();}
});
