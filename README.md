# ChatGPT Web Jjonku Writer

[**English**](README.md) | [한국어](README.ko.md)

> **Jjonku (쫀쿠)** is Korean AI-community slang for an AI subscription/account. “Web jjonku” means using the regular ChatGPT web-app allowance rather than the Codex CLI allowance.

**Let the ChatGPT web app write code in your local repo — on a usage quota separate from Codex.**

A local stdio MCP server + OpenAI Secure Tunnel that gives web ChatGPT (chatgpt.com, phone or desktop)
read/write/commit/PR access to **one repository on your machine** — with no shell exposure.

```
Web ChatGPT  →  OpenAI Secure Tunnel  →  your machine (tunnel-client)
             →  stdio MCP git writer  →  your repo  →  chatgpt/* branch  →  PR
```

---

## Why this exists

Coding-agent CLIs (Codex CLI, and anything using the `openai-codex` OAuth route) draw from the
**Codex usage pool**. When that pool runs out, the CLI stops.

OpenAI's own pricing docs state two things:

> "ChatGPT Work and Codex share usage."
>
> "Regular Chat usage isn't included."
> — <https://learn.chatgpt.com/docs/pricing>

So **regular chat on chatgpt.com is metered separately from Codex.**

### Measured, not assumed

On a real account with a hard-exhausted Codex pool:

| Check | Result |
|---|---|
| CLI credential state | `usage_limit_reached (429)`, ~19 min remaining |
| Same account, chatgpt.com, casual message | answered normally |
| Same account, chatgpt.com, coding request | answered normally |
| Account was in a Business workspace | still not merged into the Codex pool |

Conclusion: **when your coding CLI is rate-limited, the web app still works** — and this repo lets
that web session touch your actual repository instead of making you copy-paste diffs.

---

## What you get

Nine MCP tools exposed to web ChatGPT — and nothing else:

| Tool | Does |
|---|---|
| `repo_read` | read a file |
| `repo_search` | `git grep` |
| `branch_start` | create/switch to `chatgpt/<name>` off the base branch |
| `repo_write` | write a file (work branch only) |
| `git_diff` | show the working diff |
| `run_check` | run a **preconfigured** check (tests/lint) — not arbitrary commands |
| `commit_push` | commit + push the work branch |
| `pr_create` | open/reuse a PR |
| `pr_merge` | squash-merge with `--auto` (waits for required checks) |

**No shell tool. No arbitrary command execution.**

---

## Usefulness — where this actually pays off

- **Quota extension.** Your CLI pool and your web chat pool drain independently. Two budgets.
- **Phone-first coding.** Ask from a phone; a PR appears on your repo. No laptop, no VPN, no
  public port, no ngrok.
- **No copy-paste tax.** The web session edits the real files and runs your real checks, so you
  review a diff instead of transcribing one.
- **Reviewable by construction.** Everything lands on `chatgpt/*` + a PR. Nothing reaches `main`
  without your branch protection and required checks agreeing.

## Limits — read this before you build it

These are real and not fixable by configuration.

1. **This is not a fallback for your agent.**
   Your local agent (Claude Code / Codex CLI / Hermes / OpenClaw) calls tools via API tool-calling.
   The ChatGPT web app returns **prose**, not tool calls. You cannot put "web ChatGPT" into your
   agent's model fallback chain and keep tool use. If every API provider you have is exhausted,
   your agent is down; this repo does not revive it. It gives **you** a second cockpit, not your
   agent a second brain.
2. **Two brains, one repo — they cannot talk.**
   Your local agent does not see the web conversation, and vice versa. The only handoff surface is
   the repository itself (branches, commits, PRs).
3. **Requires OpenAI Secure Tunnel access.**
   Tunnel creation must associate a Platform organization with a ChatGPT workspace. If your
   account cannot open <https://platform.openai.com/settings/organization/tunnels> and create a
   tunnel with a workspace selected, stop here — nothing downstream will work.
4. **The daemon must be running.** Connector discovery and every tool call go through the local
   `tunnel-client`. If the machine sleeps or the daemon dies, the tools vanish from the chat.
5. **One repo per writer.** `repo_root` is a single path by design. Multiple repos = multiple
   writer instances/tunnels.
6. **The model is still a model.** It can write a wrong patch confidently. Required CI checks and
   PR review are load-bearing, not decorative.
7. **Provider terms are yours to check.** Automating a subscription surface may or may not fit your
   plan's terms. This repo documents a mechanism; compliance is on the operator.

---

## Security model

| Control | Enforcement |
|---|---|
| No shell | there is no shell tool; `run_check` only runs commands listed in your config |
| Path escape | resolved path must stay under `repo_root` |
| Protected paths | `deny_paths` (e.g. `.github/workflows`, `.git/config`) rejected |
| Branch discipline | writes/commits refused unless on `chatgpt/*` |
| No force-push | `git push` without `--force`; no branch deletion tool |
| Self-modification | the writer lives **outside** the repo, so it cannot edit itself or its own checks |
| Secrets | tunnel key stored `chmod 600` outside the repo |

All seven are asserted by `selfcheck.mjs`, which deliberately triggers each failure:

```
$ node selfcheck.mjs
ALL PASS (7 assertions, 5 guards)
```

Guards proving things *fail* is only half. `e2e-test.mjs` proves the happy path against a throwaway
repo and a local bare remote — branch, write, diff, run check, commit, push — and asserts `main`
never moved:

```
$ node e2e-test.mjs
E2E PASS: branch -> write -> diff -> check -> commit -> push, main untouched
```

---

## Install (macOS / Linux)

Prereqs: Node 18+, `git`, `gh` (authenticated), a repo with a remote.

```bash
git clone https://github.com/kims6305-bjk/chatgpt-web-jjonku-writer
cd chatgpt-web-jjonku-writer
./install.sh            # copies writer to ~/.local/share/webgpt-git-writer, downloads tunnel-client (checksum-verified)
```

Then, in order:

1. **Create a tunnel** — <https://platform.openai.com/settings/organization/tunnels> → *Create tunnel*.
   Fill in Name, Description, Organization, and **ChatGPT workspaces** (do not leave this empty).
   Copy the `tunnel_...` id.
2. **Create a runtime key** — <https://platform.openai.com/settings/organization/api-keys> →
   *Create new secret key* → **Restricted** → *Tunnels: Read + Use* only.
   (You do **not** need an Admin key — that is only for creating tunnels from the CLI.)
3. **Configure**:
   ```bash
   cd ~/.local/share/webgpt-git-writer
   cp writer.config.example.json writer.config.json   # set repo_root, base_branch, checks
   ./set-key.sh                                        # paste key (hidden), paste tunnel id
   node selfcheck.mjs                                  # must print ALL PASS
   ```
4. **Register the profile and start the daemon**:
   ```bash
   ./setup-tunnel.sh      # tunnel-client init + doctor
   ./install-service.sh   # launchd (macOS) or systemd --user (Linux)
   curl -fsS http://127.0.0.1:8791/readyz   # -> ready
   ```
5. **Connect ChatGPT** — with the daemon running, open
   <https://chatgpt.com/#settings/Connectors> → **⊕** (custom connector) →
   Connection: **Tunnel** → pick your tunnel → Authentication: **No authentication** →
   accept the unreviewed-server notice → Connect.

Verify end-to-end (do not trust the chat's word for it):

```bash
# ask in ChatGPT: "read the first line of README.md"
# then confirm the call actually reached your machine:
grep -c 'forwarded command to MCP server' ~/.local/share/webgpt-git-writer/tunnel.log
```

---

## Usage

In a ChatGPT conversation with the connector enabled:

- `read AGENTS.md`
- `start branch chatgpt/fix-login, patch src/auth.ts so empty passwords are rejected, run the tests, open a PR`
- `show me the diff`
- `merge it`

Everything lands on `chatgpt/*` → PR → your required checks.

---

## Agent skills (Claude Code / Codex / Hermes / OpenClaw)

`skills/` ships the same procedure in three formats so your *local* agent can install, operate and
debug this stack:

| Path | For |
|---|---|
| `skills/hermes/webgpt-tunnel-git-writer/SKILL.md` | Hermes / OpenClaw / Claude Code (`SKILL.md` + frontmatter) |
| `skills/codex/AGENTS.md` | Codex CLI (drop into repo root or merge into your `AGENTS.md`) |
| `skills/generic/PLAYBOOK.md` | any agent — plain markdown runbook |

They are generated from one source (`skills/generic/PLAYBOOK.md`); see `skills/README.md`.

---

## Repo contract for the web agent

`skills/AGENTS.snippet.md` contains the paragraph to append to your repository's `AGENTS.md`, telling
web ChatGPT it is the primary autonomous coding agent for this repo and listing what it must never do
(push to `main`, force-push, delete branches, expose secrets, weaken tests, modify workflow or writer files).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `mcp-command preflight failed: ... "/Users/you/Library/Application"` | **space in the install path** | install under a space-free path (`~/.local/share/...`) |
| Connector saves but no tools appear | Authentication set to OAuth | stdio targets expose no OAuth metadata → use **No authentication** |
| "No available tunnels" in ChatGPT | tunnel created without a ChatGPT workspace | edit the tunnel, attach the workspace |
| Connector not in the marketplace list | it is a custom connector | use the **⊕** button, not search |
| `doctor` → `control_plane_api_key FAIL` | key not exported | `set -a; . tunnel.env; set +a` before running, or use the service unit |
| Tools disappear mid-session | daemon died / machine slept | check the service; `curl /readyz` |
| Writes rejected | not on a `chatgpt/*` branch | `branch_start` first (this is intentional) |

---

## Prior art

The architecture follows a Korean community write-up describing an HTTP MCP writer behind an OpenAI
Secure Tunnel. This implementation differs in one way: `tunnel-client` supports **stdio** MCP
targets directly, so there is no HTTP server, no `/health` / `/mcp` endpoints, and no OAuth
discovery to implement — roughly a third of the moving parts.

## License

MIT
