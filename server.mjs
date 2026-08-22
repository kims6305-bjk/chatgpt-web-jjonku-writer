#!/usr/bin/env node
// stdio MCP "git writer": the smallest server that lets web ChatGPT touch ONE repo over a tunnel.
// No shell exposure. Only whitelisted check commands and fixed git/gh subcommands run.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const CFG_PATH =
  process.env.WRITER_CONFIG ??
  path.join(path.dirname(fileURLToPath(import.meta.url)), "writer.config.json");
const CFG = JSON.parse(readFileSync(CFG_PATH, "utf8"));
const ROOT = path.resolve(CFG.repo_root);
const READ_ONLY = CFG.read_only === true;
const PREFIX = CFG.branch_prefix ?? "chatgpt/";
const CHECKS = CFG.checks ?? {};           // {name: ["cmd","arg",...]}
const DENY = (CFG.deny_paths ?? [".github/workflows", ".git/config"]).map((p) => p.replace(/\/+$/, ""));

const fail = (m) => { throw new Error(m); };

function safePath(rel) {
  const abs = path.resolve(ROOT, rel);
  if (abs !== ROOT && !abs.startsWith(ROOT + path.sep)) fail(`path escapes repo: ${rel}`);
  const r = path.relative(ROOT, abs);
  if (DENY.some((d) => r === d || r.startsWith(d + path.sep))) fail(`protected path: ${r}`);
  return abs;
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { cwd: ROOT, shell: false, encoding: "utf8", maxBuffer: 8e6, ...opts });
  if (r.error) fail(`${cmd}: ${r.error.message}`);
  return { code: r.status, stdout: (r.stdout || "").slice(-60000), stderr: (r.stderr || "").slice(-20000) };
}

function currentBranch() {
  return run("git", ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.trim();
}
function requireWorkBranch() {
  const b = currentBranch();
  if (!b.startsWith(PREFIX)) fail(`refuse: branch '${b}' is not ${PREFIX}*`);
  return b;
}

const TOOLS = {
  repo_read: {
    readOnly: true,
    desc: "Read a file in the repo.",
    schema: { type: "object", properties: { path: { type: "string" } }, required: ["path"] },
    fn: ({ path: p }) => readFileSync(safePath(p), "utf8"),
  },
  repo_search: {
    readOnly: true,
    desc: "git grep in the repo.",
    schema: { type: "object", properties: { pattern: { type: "string" } }, required: ["pattern"] },
    fn: ({ pattern }) => run("git", ["grep", "-n", "--", pattern]).stdout || "(no match)",
  },
  repo_write: {
    desc: "Write a file (full content). Only on a chatgpt/* branch.",
    schema: {
      type: "object",
      properties: { path: { type: "string" }, content: { type: "string" } },
      required: ["path", "content"],
    },
    fn: ({ path: p, content }) => {
      requireWorkBranch();
      const abs = safePath(p);
      mkdirSync(path.dirname(abs), { recursive: true });
      writeFileSync(abs, content);
      return `wrote ${p} (${content.length} bytes)`;
    },
  },
  branch_start: {
    desc: "Create and switch to a chatgpt/<name> branch from the base branch.",
    schema: { type: "object", properties: { name: { type: "string" } }, required: ["name"] },
    fn: ({ name }) => {
      const b = name.startsWith(PREFIX) ? name : PREFIX + name;
      if (!/^[\w./-]+$/.test(b)) fail("bad branch name");
      run("git", ["fetch", "origin", CFG.base_branch]);
      const r = run("git", ["checkout", "-B", b, `origin/${CFG.base_branch}`]);
      return `${r.stdout}${r.stderr}`;
    },
  },
  git_diff: {
    readOnly: true,
    desc: "Show the working diff (staged + unstaged).",
    schema: { type: "object", properties: {} },
    fn: () => run("git", ["diff", "HEAD"]).stdout || "(clean)",
  },
  run_check: {
    desc: `Run a preconfigured check. Available: ${Object.keys(CHECKS).join(", ") || "(none)"}`,
    schema: { type: "object", properties: { name: { type: "string" } }, required: ["name"] },
    fn: ({ name }) => {
      const c = CHECKS[name] ?? fail(`unknown check: ${name}`);
      const r = run(c[0], c.slice(1));
      return `exit=${r.code}\n${r.stdout}\n${r.stderr}`;
    },
  },
  commit_push: {
    desc: "Commit all changes and push the chatgpt/* branch.",
    schema: { type: "object", properties: { message: { type: "string" } }, required: ["message"] },
    fn: ({ message }) => {
      const b = requireWorkBranch();
      run("git", ["add", "-A"]);
      const c = run("git", ["commit", "-m", message]);
      const p = run("git", ["push", "-u", "origin", b]); // no --force, ever
      return `commit exit=${c.code}\n${c.stdout}\npush exit=${p.code}\n${p.stderr}`;
    },
  },
  pr_create: {
    desc: "Open (or reuse) a PR from the current chatgpt/* branch.",
    schema: {
      type: "object",
      properties: { title: { type: "string" }, body: { type: "string" } },
      required: ["title"],
    },
    fn: ({ title, body }) => {
      requireWorkBranch();
      const r = run("gh", ["pr", "create", "--base", CFG.base_branch, "--title", title, "--body", body ?? ""]);
      if (r.code !== 0 && /already exists/i.test(r.stderr)) return run("gh", ["pr", "view", "--json", "url"]).stdout;
      return `${r.stdout}${r.stderr}`;
    },
  },
  pr_merge: {
    desc: "Squash-merge the current PR (waits for required checks).",
    schema: { type: "object", properties: {} },
    fn: () => {
      requireWorkBranch();
      const r = run("gh", ["pr", "merge", "--squash", "--delete-branch", "--auto"]);
      return `exit=${r.code}\n${r.stdout}${r.stderr}`;
    },
  },
};

// ---- minimal MCP stdio (JSON-RPC 2.0, line-delimited) ----
const send = (o) => process.stdout.write(JSON.stringify(o) + "\n");

function handle(req) {
  const { id, method, params } = req;
  if (method === "initialize")
    return {
      protocolVersion: "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "webgpt-git-writer", version: "1" },
    };
  if (method === "tools/list")
    return {
      tools: Object.entries(TOOLS)
        .filter(([, t]) => !READ_ONLY || t.readOnly)
        .map(([name, t]) => ({
          name,
          description: t.desc,
          inputSchema: t.schema,
          annotations: { readOnlyHint: t.readOnly === true },
        })),
    };
  if (method === "tools/call") {
    const t = TOOLS[params.name] ?? fail(`unknown tool: ${params.name}`);
    if (READ_ONLY && !t.readOnly) fail(`tool unavailable in read-only mode: ${params.name}`);
    return { content: [{ type: "text", text: String(t.fn(params.arguments ?? {})) }] };
  }
  fail(`unknown method: ${method}`);
}

let buf = "";
process.stdin.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let req;
    try { req = JSON.parse(line); } catch { continue; }
    if (req.id === undefined) continue; // notification
    try {
      send({ jsonrpc: "2.0", id: req.id, result: handle(req) });
    } catch (e) {
      send({ jsonrpc: "2.0", id: req.id, error: { code: -32000, message: e.message } });
    }
  }
});

if (!existsSync(ROOT)) { console.error(`repo_root missing: ${ROOT}`); process.exit(2); }
