"use strict";
const attempts = new Map();
const WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 5;
function keyFor(login, ip) { return String(login).toLowerCase() + "|" + String(ip); }
function allowed(login, ip, now = Date.now()) {
  const key = keyFor(login, ip);
  const entry = attempts.get(key);
  if (!entry || now - entry.started >= WINDOW_MS) return true;
  return entry.count < MAX_ATTEMPTS;
}
function recordFailure(login, ip, now = Date.now()) {
  const key = keyFor(login, ip);
  const entry = attempts.get(key);
  if (!entry || now - entry.started >= WINDOW_MS) attempts.set(key, { count: 1, started: now });
  else entry.count++;
  if (attempts.size > 10000) attempts.clear();
}
function clear(login, ip) { attempts.delete(keyFor(login, ip)); }
module.exports = { allowed, recordFailure, clear };
