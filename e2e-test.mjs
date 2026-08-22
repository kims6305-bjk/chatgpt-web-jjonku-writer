#!/usr/bin/env node
// End-to-end write-path test: branch -> write -> check -> commit -> push, against a local bare remote.
// Proves the tools that selfcheck.mjs only proves *refuse* correctly can also *succeed*.
import { spawn } from "node:child_process";
import { execFileSync } from "node:child_process";
import assert from "node:assert";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const CFG = JSON.parse(readFileSync(path.join(HOME, "writer.config.json"), "utf8"));
const ROOT = CFG.repo_root;

const p = spawn("node", [path.join(HOME, "server.mjs")], { stdio: ["pipe", "pipe", "inherit"] });
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
  new Promise((res) => { const n = ++id; pending.set(n, res); p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: n, method, params }) + "\n"); });
const tool = (name, args) => call("tools/call", { name, arguments: args });
const git = (...a) => execFileSync("git", a, { cwd: ROOT, encoding: "utf8" }).trim();

await call("initialize", {});

const r1 = await tool("branch_start", { name: "e2e-test" });
assert.ok(!r1.error, `branch_start failed: ${r1.error?.message}`);
assert.equal(git("rev-parse", "--abbrev-ref", "HEAD"), "chatgpt/e2e-test", "branch not switched");

const r2 = await tool("repo_write", { path: "app.py", content: "def f():\n    return 42\n" });
assert.ok(!r2.error, `repo_write failed: ${r2.error?.message}`);
assert.match(readFileSync(path.join(ROOT, "app.py"), "utf8"), /return 42/, "file content not written");

const r3 = await tool("git_diff", {});
assert.match(r3.result.content[0].text, /return 42/, "diff does not show the change");

const check = Object.keys(CFG.checks)[0];
const r4 = await tool("run_check", { name: check });
assert.match(r4.result.content[0].text, /^exit=0/, `check ${check} did not pass`);

const r5 = await tool("commit_push", { message: "e2e: bump return value" });
assert.ok(!r5.error, `commit_push failed: ${r5.error?.message}`);
assert.equal(git("log", "-1", "--pretty=%s"), "e2e: bump return value", "commit subject wrong");

const remote = git("ls-remote", "--heads", "origin", "chatgpt/e2e-test");
assert.match(remote, /chatgpt\/e2e-test/, "branch did not reach the remote");

const mainSha = git("rev-parse", "origin/main");
const branchSha = git("rev-parse", "chatgpt/e2e-test");
assert.notEqual(mainSha, branchSha, "work landed on main");

console.log("E2E PASS: branch -> write -> diff -> check -> commit -> push, main untouched");
p.kill();
