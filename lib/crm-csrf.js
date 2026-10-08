"use strict";
function requireTrustedOrigin(req, res, next) {
 if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return next();
 const origin = req.get("origin");
 const host = req.get("host");
 const scheme = req.secure || process.env.NODE_ENV === "production" ? "https" : "http";
 if (!origin || !host || origin !== scheme + "://" + host) {
  return res.status(403).json({ok:false,error:"untrusted_origin"});
 }
 next();
}
module.exports = { requireTrustedOrigin };
