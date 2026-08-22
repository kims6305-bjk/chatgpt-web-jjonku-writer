#!/usr/bin/env node
// Self-check for server.mjs. Speaks the real stdio protocol and asserts every guard fails closed.
// usage: node selfcheck.mjs
import { spawn } from "node:child_process";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const CFG = path.join(HOME, "writer.config.json");

const p = spawn("node", [path.join(HOME, "server.mjs")], {
  env: { ...process.env, WRITER_CONFIG: CFG },
  stdio: ["pipe", "pipe", "inherit"],
});

let buf = "";
const pending = new Map();
p.stdout.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    const m = JSON.parse(line);
    pending.get(m.id)?.(m);
    pending.delete(m.id);
  }
});

let id = 0;
const call = (method, params) =>
  new Promise((res) => {
    const n = ++id;
    pending.set(n, res);
    p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: n, method, params }) + "\n");
  });

const tool = (name, args) => call("tools/call", { name, arguments: args });

const init = await call("initialize", {});
assert.equal(init.result.serverInfo.name, "webgpt-git-writer", "initialize");

const list = await call("tools/list", {});
const names = list.result.tools.map((t) => t.name);
for (const n of ["repo_read", "repo_write", "branch_start", "commit_push", "pr_create", "pr_merge", "run_check"])
  assert.ok(names.includes(n), `tool missing: ${n}`);

// read works
const probe = process.env.SELFCHECK_READ ?? "README.md";
const r1 = await tool("repo_read", { path: probe });
assert.ok(r1.result.content[0].text.length > 10, `repo_read ${probe}`);

// GUARD 1: path escape refused
const r2 = await tool("repo_read", { path: "../../.ssh/id_rsa" });
assert.match(r2.error.message, /escapes repo/, "path escape must be refused");

// GUARD 2: protected path refused
const r3 = await tool("repo_read", { path: ".github/workflows/ci.yml" });
assert.match(r3.error.message, /protected path/, "deny_paths must be refused");

// GUARD 3: write refused off a chatgpt/* branch
const r4 = await tool("repo_write", { path: "tmp_probe.txt", content: "x" });
assert.match(r4.error.message, /not chatgpt\//, "write off work-branch must be refused");

// GUARD 4: commit refused off a chatgpt/* branch
const r5 = await tool("commit_push", { message: "probe" });
assert.match(r5.error.message, /not chatgpt\//, "commit off work-branch must be refused");

// GUARD 5: unknown check refused
const r6 = await tool("run_check", { name: "rm -rf /" });
assert.match(r6.error.message, /unknown check/, "arbitrary check must be refused");

// configured check runs
const checks = Object.keys(JSON.parse(readFileSync(path.join(HOME, "writer.config.json"), "utf8")).checks ?? {});
if (checks.length) {
  const r7 = await tool("run_check", { name: checks[0] });
  assert.match(r7.result.content[0].text, /^exit=/, `run_check ${checks[0]}`);
}

console.log("ALL PASS (7 assertions, 5 guards)");
p.kill();
