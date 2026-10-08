"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { Pool } = require("pg");
const { createSession, lookupSession } = require("../lib/crm-session-store");
const { newSession } = require("../lib/crm-auth");
test("disabled account and expired session cannot authenticate", {skip:!process.env.CRM_TEST_DATABASE_URL}, async()=>{
 const db=new Pool({connectionString:process.env.CRM_TEST_DATABASE_URL,ssl:false,max:1});
 const id=crypto.randomUUID();
 const login="state_"+crypto.randomBytes(8).toString("hex");
 try {
  await db.query(`CREATE TABLE IF NOT EXISTS crm_staff (
   id UUID PRIMARY KEY,login TEXT NOT NULL UNIQUE,password_salt TEXT NOT NULL,
   password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK (role IN ('owner','master')),
   enabled BOOLEAN NOT NULL DEFAULT TRUE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await db.query(`CREATE TABLE IF NOT EXISTS crm_staff_sessions (
   id UUID PRIMARY KEY,staff_id UUID NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
   token_hash TEXT NOT NULL UNIQUE,expires_at TIMESTAMPTZ NOT NULL,
   revoked_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await db.query("INSERT INTO crm_staff(id,login,password_salt,password_hash,role) VALUES($1,$2,'test','test','master')",[id,login]);
  const session=newSession();
  await createSession(db,id,session);
  assert.equal((await lookupSession(db,session.token)).role,"master");
  await db.query("UPDATE crm_staff SET enabled=FALSE WHERE id=$1",[id]);
  assert.equal(await lookupSession(db,session.token),null);
  await db.query("UPDATE crm_staff SET enabled=TRUE WHERE id=$1",[id]);
  await db.query("UPDATE crm_staff_sessions SET expires_at=NOW()-INTERVAL '1 second' WHERE staff_id=$1",[id]);
  assert.equal(await lookupSession(db,session.token),null);
 } finally {
  await db.query("DELETE FROM crm_staff WHERE id=$1",[id]).catch(()=>{});
  await db.end();
 }
});
