#!/usr/bin/env node
// Negative-control gate for the personal Pro profile: only read/fetch tools may be visible or callable.
import { spawn } from "node:child_process";
import assert from "node:assert";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const cfg = JSON.parse(readFileSync(path.join(HOME, "writer.config.json"), "utf8"));
assert.equal(cfg.read_only, true, "writer.config.json must set read_only=true");
assert.ok(cfg.deny_paths?.length, "at least one deny_path is required");

const p = spawn("node", [path.join(HOME, "server.mjs")], { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
const pending = new Map();
p.stdout.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line) continue;
    const m = JSON.parse(line); pending.get(m.id)?.(m); pending.delete(m.id);
  }
});
let id = 0;
const call = (method, params) => new Promise((res) => {
  const n = ++id; pending.set(n, res);
  p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: n, method, params }) + "\n");
});
const tool = (name, args = {}) => call("tools/call", { name, arguments: args });

await call("initialize", {});
const list = await call("tools/list", {});
const names = list.result.tools.map((t) => t.name).sort();
assert.deepEqual(names, ["git_diff", "repo_read", "repo_search"], "read-only tool surface changed");
assert.ok(list.result.tools.every((t) => t.annotations?.readOnlyHint === true), "every exposed tool must carry readOnlyHint");

const probe = process.env.SELFCHECK_READ ?? "README.md";
const read = await tool("repo_read", { path: probe });
assert.ok(read.result.content[0].text.length > 0, "repo_read failed");
const escape = await tool("repo_read", { path: "../../.ssh/id_rsa" });
assert.match(escape.error.message, /escapes repo/, "path escape was not refused");
const denied = await tool("repo_read", { path: cfg.deny_paths[0] });
assert.match(denied.error.message, /protected path/, "deny_path was not refused");

for (const name of ["repo_write", "branch_start", "run_check", "commit_push", "pr_create", "pr_merge"]) {
  const r = await tool(name, {});
  assert.match(r.error.message, /unavailable in read-only mode/, `${name} was callable`);
}

console.log("READ-ONLY PASS: 3 read tools exposed, 6 mutation tools hidden and fail-closed");
p.kill();
