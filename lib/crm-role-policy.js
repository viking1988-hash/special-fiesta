"use strict";
function requiredRole(method, path) {
  const draftCreate = method === "POST" && path === "/drafts";
  const draftRead = method === "GET" && /^\/drafts\/[^/]+$/.test(path);
  return draftCreate || draftRead ? "master" : "owner";
}
function permitted(role, method, path) {
  if (role !== "owner" && role !== "master") return false;
  const required = requiredRole(method, path);
  return role === "owner" || required === "master";
}
module.exports = { requiredRole, permitted };
