# ChatGPT Web Jjonku Writer

[**English**](README.md) | [한국어](README.ko.md)

> **Jjonku (쫀쿠)** is Korean AI-community slang for an AI subscription/account. “Web jjonku” means using the regular ChatGPT web-app allowance rather than the Codex CLI allowance.

**Let the ChatGPT web app write code in your local repo — on a usage quota separate from Codex.**

A local stdio MCP server + OpenAI Secure Tunnel that gives web ChatGPT (chatgpt.com, phone or desktop)
read/write/commit/PR access to **one repository on your machine** — with no shell exposure.

> **Plan behavior:** this repository ships the same guarded 9-tool writer for every account. It is
> end-to-end verified on **Business**. The current ChatGPT pricing page lists Developer mode for both
> **Plus and Pro**, so personal accounts should try the full profile first. OpenAI's separate MCP help
> page still says full write/modify is officially supported only on Business/Enterprise/Edu and Pro is
> read/fetch-only; therefore Plus/Pro full write remains **account-rollout dependent** until observed.
> Sources: [MCP help](https://help.openai.com/en/articles/12584461) and
> [ChatGPT pricing](https://chatgpt.com/pricing).
>
> **Luna:** OpenAI lists GPT-5.6 Luna for Plus and unlimited for Pro, and documents Luna in Work/Codex.
> Use Luna with the full profile when the account exposes all actions; if write tools are rejected or
> omitted during tool scan, switch to the bundled fail-closed read-only profile.

### Two supported profiles

| Profile | Plan | Exposed tools | Status |
|---|---|---|---|
| Full writer | Business / Enterprise / Edu | all 9 tools: read, write, checks, commit, PR, merge | Business E2E verified |
| Try full writer first | Plus / Pro | the same 9 tools | Developer mode documented; write actions depend on account rollout |
| Personal read-only fallback | Plus / Pro | `repo_read`, `repo_search`, `git_diff` only | code + fresh-box verified |

Personal accounts try the full profile first. Fall back only if write tools are omitted or rejected.
The fallback is fail-closed: mutation tools are omitted from discovery **and** rejected when called
directly. Free and Go do not currently expose Developer mode.

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

   # Choose ONE profile, then edit repo_root / base_branch / deny_paths:

   # Business / Enterprise / Edu / Plus / Pro — try full read/write first
   cp writer.config.example.json writer.config.json
   $EDITOR writer.config.json             # set repo_root / base_branch / deny_paths
   node selfcheck.mjs                     # must print ALL PASS

   # Plus/Pro fallback when write actions are omitted or rejected
   # cp writer.config.personal-pro.example.json writer.config.json
   # $EDITOR writer.config.json
   # node selfcheck-readonly.mjs          # must print READ-ONLY PASS

   ./set-key.sh                         # paste key (hidden), paste tunnel id
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

## Optional: hand tasks back to your local agent (`handoff`)

Off by default. Add a `handoff` block to `writer.config.json` and ChatGPT gets a 10th tool:

```json
"handoff": {
  "inbox": "/absolute/path/handoff/requests.jsonl",
  "notify": ["/absolute/path/notify.sh"]
}
```

- ChatGPT calls `handoff{task}` when you say "pass this to my agent" (or the task needs the machine itself).
- The server **never executes anything**. It appends `{id, ts, task}` to `inbox` and pipes a message ending in
  `approve #<id>` to `notify` on stdin (any command: Telegram/Slack/ntfy/`osascript`, or omit it).
- You review the message and send `approve #<id>` to your local agent; the agent reads that line from `inbox`
  and does the work. Always quote the id — a bare "yes" is ambiguous once two requests are queued.
- Why the human gate: web ChatGPT reads web pages, and page text can steer it (prompt injection).
  A queue + approval keeps that text from ever reaching a shell on its own.
- Cost: everything up to the queue uses only your ChatGPT web quota. The approved task runs on your local
  agent's model, so hand off only what really needs the machine.

```bash
node selfcheck-handoff.mjs   # HANDOFF ALL PASS (hidden when unconfigured, empty refused, never executes, notify failure surfaced)
```

---

## Optional: a local web page that asks web ChatGPT (`webgpt/`)

The writer above lets ChatGPT reach your repo. `webgpt/` is the other direction: **you (or your scripts) ask
web ChatGPT from a local page**, so heavy questions and small coding jobs run on your ChatGPT web quota instead
of your API / CLI-agent limits.

> ⚠️ **Read first.** This drives the logged-in ChatGPT web page with browser automation
> ([Aside](https://aside.com) `aside repl`: scripted, no Aside LLM involved). Automating the consumer web UI is
> very likely against OpenAI's terms and can get the account limited. The page structure also changes without
> notice — selectors here were last verified 2026-10. Use your own account, at your own risk, or don't.

| Tab | What happens |
|---|---|
| **Ask** | question → temporary chat → answer on the page (multi-minute answers OK, concurrent requests queue) |
| **Code** | you write `test_main.py`; web GPT writes `solution.py`; it runs **here**; failures go back (max 3 rounds); output files downloadable |
| **Skills** | your own `SKILL.md` files can be attached: `#name`, picker, or auto-pick by word overlap (0 tokens) |

```bash
cd webgpt
cp webgpt.config.example.json webgpt.config.json   # aside path, data_dir, python venv
python3 webgpt.py skills init     # questionnaire: your skill folders + your private words -> allowlist
python3 webgpt.py selftest        # live "1+1" round trip
python3 app.py                    # http://127.0.0.1:8790
python3 test_webgpt.py            # offline (fake browser): WEBGPT OFFLINE ALL PASS
```

**Skills never leave unchecked.** `skills init` scans every `SKILL.md` in the folders you name and holds back
anything with home paths, e-mails, keys/tokens, private IPs, or the private words you typed (name, company,
clients). Only the allowlist you confirm is sent, and every send re-checks the text, so a skill that later gains
private content is blocked again. It is a word filter, not a guarantee: read the allowlist.

**Code mode runs model-written code on your machine.** The test is yours (the model never grades itself), but
point `python` at a throwaway venv or container, and keep `app.py` on localhost (set `WEBGPT_TOKEN` otherwise).

Settings worth knowing: `effort` + `model_button_label` (the model picker's aria-label in *your* UI language)
pin reasoning effort each run; leave both `null` to skip. `notify` gets results on stdin (Telegram/Slack/ntfy).

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
