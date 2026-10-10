"use strict";
const crypto=require("node:crypto");
const WINDOW_SECONDS=900;
const MAX_ATTEMPTS=5;
function keyFor(login,ip){
 const normalized=String(login||"").trim().toLowerCase();
 const address=String(ip||"unknown").trim();
 return crypto.createHash("sha256").update(JSON.stringify([normalized,address])).digest("hex");
}
async function allowed(db,login,ip){
 if(!db||typeof db.query!=="function")throw Error("throttle_unavailable");
 const key=keyFor(login,ip);
 const result=await db.query(
  "SELECT failures FROM crm_login_attempts WHERE key_hash=$1 AND window_start>NOW()-INTERVAL '15 minutes' LIMIT 1",
  [key]
 );
 return !result.rows.length||Number(result.rows[0].failures)<MAX_ATTEMPTS;
}
async function recordFailure(db,login,ip){
 if(!db||typeof db.query!=="function")throw Error("throttle_unavailable");
 const key=keyFor(login,ip);
 await db.query(
  `INSERT INTO crm_login_attempts(key_hash,failures,window_start) VALUES($1,1,NOW())
   ON CONFLICT(key_hash) DO UPDATE SET
   failures=CASE WHEN crm_login_attempts.window_start<=NOW()-INTERVAL '15 minutes' THEN 1 ELSE crm_login_attempts.failures+1 END,
   window_start=CASE WHEN crm_login_attempts.window_start<=NOW()-INTERVAL '15 minutes' THEN NOW() ELSE crm_login_attempts.window_start END`,
  [key]
 );
}
async function clear(db,login,ip){
 if(!db||typeof db.query!=="function")throw Error("throttle_unavailable");
 await db.query("DELETE FROM crm_login_attempts WHERE key_hash=$1",[keyFor(login,ip)]);
}
module.exports={allowed,recordFailure,clear,keyFor,WINDOW_SECONDS,MAX_ATTEMPTS};
