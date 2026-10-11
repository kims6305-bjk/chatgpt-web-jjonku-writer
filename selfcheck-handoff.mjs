#!/usr/bin/env node
// Self-check for the optional `handoff` tool. Uses a throwaway repo + config; touches nothing real.
// usage: node selfcheck-handoff.mjs
import { spawn, spawnSync } from "node:child_process";
import assert from "node:assert";
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HOME = path.dirname(fileURLToPath(import.meta.url));
const T = mkdtempSync(path.join(tmpdir(), "handoff-"));
const repo = path.join(T, "repo");
spawnSync("git", ["init", "-q", repo]);
const inbox = path.join(T, "inbox", "requests.jsonl");
const notified = path.join(T, "notified.txt");

function start(cfg) {
  const c = path.join(T, `cfg-${Math.random()}.json`);
  writeFileSync(c, JSON.stringify({ repo_root: repo, deny_paths: [".git/config"], ...cfg }));
  const p = spawn("node", [path.join(HOME, "server.mjs")], { env: { ...process.env, WRITER_CONFIG: c }, stdio: ["pipe", "pipe", "inherit"] });
  let buf = "", id = 0;
  const pending = new Map();
  p.stdout.on("data", (d) => {
    buf += d;
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const m = JSON.parse(buf.slice(0, i));
      buf = buf.slice(i + 1);
      pending.get(m.id)?.(m);
    }
  });
  const call = (method, params) => new Promise((res) => {
    const n = ++id;
    pending.set(n, res);
    p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: n, method, params }) + "\n");
  });
  return { p, call, tool: (name, args) => call("tools/call", { name, arguments: args }) };
}
const names = async (s) => (await s.call("tools/list", {})).result.tools.map((t) => t.name);

// 1. off by default: no handoff config -> tool not exposed, call refused
const off = start({});
assert.ok(!(await names(off)).includes("handoff"), "handoff must be hidden when unconfigured");
assert.match((await off.tool("handoff", { task: "x" })).error.message, /unknown tool/, "unconfigured call refused");
off.p.kill();

// 2. on: queues + notifies, never executes
const on = start({ handoff: { inbox, notify: ["sh", "-c", `cat > '${notified}'`] } });
assert.ok((await names(on)).includes("handoff"), "handoff exposed when configured");
assert.match((await on.tool("handoff", { task: "   " })).error.message, /empty task/, "empty task refused");
assert.ok(!existsSync(inbox), "refused task must not be queued");
const marker = path.join(T, "pwned");
const r = await on.tool("handoff", { task: `touch ${marker}; $(touch ${marker})` });
const id = r.result.content[0].text.match(/#(\w+)/)[1];
const line = JSON.parse(readFileSync(inbox, "utf8").trim());
assert.equal(line.id, id, "queued with returned id");
assert.match(readFileSync(notified, "utf8"), new RegExp(`approve #${id}`), "notify got approve hint");
assert.ok(!existsSync(marker), "task text must never execute");
on.p.kill();

// 3. failing notifier surfaces an error (request still queued, user is told)
const bad = start({ handoff: { inbox, notify: ["false"] } });
assert.match((await bad.tool("handoff", { task: "y" })).error.message, /notify failed/, "notify failure reported");
bad.p.kill();

console.log("HANDOFF ALL PASS (9 assertions)");
