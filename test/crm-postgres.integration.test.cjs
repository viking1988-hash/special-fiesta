"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { Pool } = require("pg");
const { createSession, lookupSession, revokeSession } = require("../lib/crm-session-store");
const { newSession } = require("../lib/crm-auth");

test("PostgreSQL staff sessions persist and revoke", {skip:!process.env.CRM_TEST_DATABASE_URL}, async () => {
 const pool=new Pool({connectionString:process.env.CRM_TEST_DATABASE_URL,ssl:false,max:1});
 const id=crypto.randomUUID();
 const login="integration_"+crypto.randomBytes(8).toString("hex");
 try {
  await pool.query(`CREATE TABLE IF NOT EXISTS crm_staff (
   id UUID PRIMARY KEY, login TEXT NOT NULL UNIQUE, password_salt TEXT NOT NULL,
   password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('owner','master')),
   enabled BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await pool.query(`CREATE TABLE IF NOT EXISTS crm_staff_sessions (
   id UUID PRIMARY KEY, staff_id UUID NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
   token_hash TEXT NOT NULL UNIQUE, expires_at TIMESTAMPTZ NOT NULL,
   revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
  await pool.query("INSERT INTO crm_staff(id,login,password_salt,password_hash,role) VALUES($1,$2,'test','test','owner')",[id,login]);
  const session=newSession();
  await createSession(pool,id,session);
  assert.equal((await lookupSession(pool,session.token)).login,login);
  assert.equal(await revokeSession(pool,session.token),true);
  assert.equal(await lookupSession(pool,session.token),null);
 } finally {
  await pool.query("DELETE FROM crm_staff WHERE id=$1",[id]).catch(()=>{});
  await pool.end();
 }
});
