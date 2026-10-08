"use strict";
function requireTrustedOrigin(req, res, next) {
 if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return next();
 const origin = req.get("origin");
 const host = req.get("host");
 const forwarded = req.get("x-forwarded-proto");
 const scheme = forwarded === "https" ? "https" : (req.secure ? "https" : "http");
 if (!origin || !host || origin !== scheme + "://" + host) {
  return res.status(403).json({ok:false,error:"untrusted_origin"});
 }
 next();
}
module.exports = { requireTrustedOrigin };
