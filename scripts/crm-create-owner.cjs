"use strict";
const crypto = require("node:crypto");
const { Pool } = require("pg");
async function main() {
 const url = process.env.DATABASE_URL;
 const login = String(process.env.CRM_OWNER_LOGIN || "").trim().toLowerCase();
 const password = process.env.CRM_OWNER_PASSWORD;
 if (!url || !/^[a-z0-9._-]{3,100}$/.test(login) || typeof password !== "string" || password.length < 16) {
  throw Error("Set DATABASE_URL, CRM_OWNER_LOGIN (3-100 safe chars), CRM_OWNER_PASSWORD (16+ chars)");
 }
 if (process.env.CRM_OWNER_BOOTSTRAP_CONFIRM !== "YES") throw Error("Set CRM_OWNER_BOOTSTRAP_CONFIRM=YES to authorize owner provisioning");
 const pool = new Pool({connectionString:url,max:1});
 try {
  const salt = crypto.randomBytes(32).toString("hex");
  const hash = crypto.scryptSync(password,salt,64).toString("hex");
  const result = await pool.query(
   "INSERT INTO crm_staff(id,login,password_salt,password_hash,role,enabled) VALUES($1,$2,$3,$4,'owner',TRUE) ON CONFLICT (login) DO NOTHING RETURNING id",
   [crypto.randomUUID(),login,salt,hash]
  );
  if (!result.rowCount) throw Error("Account already exists; no credentials changed");
  process.stdout.write("Owner account created successfully\n");
 } finally { await pool.end(); }
}
main().catch(e=>{console.error("Owner provisioning failed:",e.message);process.exitCode=1;});
