"use strict";
const { Pool } = require("pg");
async function main() {
 if (!process.env.DATABASE_URL) throw Error("DATABASE_URL is required");
 const pool = new Pool({connectionString:process.env.DATABASE_URL,ssl:false,max:1});
 try {
  await pool.query("BEGIN");
  await pool.query(`CREATE TABLE IF NOT EXISTS crm_staff (
   id UUID PRIMARY KEY,
   login TEXT NOT NULL UNIQUE,
   password_salt TEXT NOT NULL,
   password_hash TEXT NOT NULL,
   role TEXT NOT NULL CHECK (role IN ('owner','master')),
   enabled BOOLEAN NOT NULL DEFAULT TRUE,
   created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`);
  await pool.query(`CREATE TABLE IF NOT EXISTS crm_staff_sessions (
   id UUID PRIMARY KEY,
   staff_id UUID NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
   token_hash TEXT NOT NULL UNIQUE,
   expires_at TIMESTAMPTZ NOT NULL,
   revoked_at TIMESTAMPTZ,
   created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`);
  await pool.query("COMMIT");
  process.stdout.write("CRM staff schema ready\n");
 } catch (e) {await pool.query("ROLLBACK");throw e;}
 finally {await pool.end();}
}
main().catch(e=>{console.error("CRM schema setup failed:",e.message);process.exitCode=1;});
