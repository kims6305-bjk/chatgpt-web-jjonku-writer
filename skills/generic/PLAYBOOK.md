# Playbook — webgpt-git-writer

Give the ChatGPT **web app** read/write/commit/PR access to one local repository, over an OpenAI
Secure Tunnel, with no shell exposure. Useful because web chat is metered separately from the
Codex pool your coding CLI drains.

## When to use this

- The user says their coding CLI hit a usage limit and wants to keep working from chatgpt.com.
- The user asks to install / repair / operate a local MCP "git writer" behind an OpenAI tunnel.
- Tools defined here (`repo_read`, `branch_start`, `pr_create`, ...) show up in a ChatGPT connector
  and stop working.

## When NOT to use this

- The user wants their **agent** to fall back to web ChatGPT. It cannot: the web app returns prose,
  not tool calls. Say so plainly instead of building a bridge that loses tool use.
- The user wants multiple repos from one writer. Run one writer + tunnel per repo instead.

## Architecture

```
Web ChatGPT → OpenAI Secure Tunnel → tunnel-client (local daemon)
            → stdio MCP git writer → repo → chatgpt/* branch → PR
```

`tunnel-client` supports **stdio** MCP targets, so no HTTP server, no `/health` or `/mcp`
endpoints, and no OAuth discovery need to be implemented.

## Layout

| Path | Purpose |
|---|---|
| `~/.local/share/webgpt-git-writer/server.mjs` | the MCP writer (must live OUTSIDE the repo) |
| `.../writer.config.json` | `repo_root`, `base_branch`, `deny_paths`, `checks` |
| `.../selfcheck.mjs` | guard assertions; must print `ALL PASS` |
| `.../tunnel.env` | runtime key + tunnel id, chmod 600 |
| `~/.config/tunnel-client/webgpt-writer.yaml` | tunnel-client profile |
| `.../tunnel.log` | proof of what ChatGPT actually called |

The writer lives outside the repo on purpose: it must not be able to edit itself or its own checks.

## Install

1. `./install.sh` — copies the writer to a space-free path, downloads tunnel-client, verifies SHA256.
2. Create a tunnel at `https://platform.openai.com/settings/organization/tunnels`.
   **Fill the ChatGPT workspaces field.** Empty means "No available tunnels" later.
3. Create a runtime key at `https://platform.openai.com/settings/organization/api-keys`:
   Restricted → **Tunnels: Read + Use**. An Admin key (`sk-admin-`) is only needed to create tunnels
   from the CLI; if the tunnel was made in the UI, skip it.
4. `cp writer.config.example.json writer.config.json` and set `repo_root` / `checks`.
5. `./set-key.sh` (hidden input) → `node selfcheck.mjs` → must print `ALL PASS`.
6. `./setup-tunnel.sh` → `tunnel-client doctor` must print `RESULT ok`.
7. `./install-service.sh` → launchd/systemd, then `curl -fsS http://127.0.0.1:8791/readyz` → `ready`.
8. With the daemon up, open `https://chatgpt.com/#settings/Connectors` → **⊕** →
   Connection: **Tunnel** → your tunnel → Authentication: **No authentication** → accept the
   unreviewed-server notice → Connect.

## Verify (do not trust self-reports)

Ask the chat to read a known file, then confirm the call reached the machine:

```bash
grep -c 'forwarded command to MCP server' ~/.local/share/webgpt-git-writer/tunnel.log
```

Compare the file's real content with what the chat printed. A model can produce a plausible file
without ever calling the tool; the log and a byte-level comparison are what settle it.

`./verify.sh` bundles daemon + doctor + guards + call count into one report.

## Guards (asserted by selfcheck.mjs)

1. path escaping `repo_root` → refused
2. `deny_paths` → refused
3. `repo_write` off a `chatgpt/*` branch → refused
4. `commit_push` off a `chatgpt/*` branch → refused
5. `run_check` with an unregistered name → refused

Plus: no shell tool, no `--force` push, no branch deletion, writer outside the repo.

Change any guard and re-run `selfcheck.mjs`. If a guard stops failing, it stopped being a guard.

## Pitfalls (each one observed in practice)

- **No spaces in the install path.** `~/Library/Application Support/...` makes tunnel-client split
  `mcp.command` at the space and preflight fails on `/Users/you/Library/Application`.
- **Authentication must be "No authentication".** stdio targets expose no OAuth metadata
  (`doctor` reports `oauth_metadata SKIP`). Selecting OAuth makes discovery fail.
- **The connector is not in the marketplace list.** Use the ⊕ button to add a custom connector.
- **Tunnel without a ChatGPT workspace** → "No available tunnels" in the connector picker.
- **Admin key is usually unnecessary** — only for `tunnel-client admin tunnels create`.
- **`WRITER_CONFIG` may be unset** under a service manager; `server.mjs` falls back to
  `writer.config.json` beside itself.
- **`new URL(import.meta.url).pathname` leaves `%20`** on paths with spaces; use `fileURLToPath`.
- **Do not run the daemon as a child of an agent session.** It dies when the agent restarts. Use
  launchd/systemd.

## Operating

Enable the connector in a conversation, then speak normally:

- `read AGENTS.md`
- `start branch chatgpt/fix-login, patch src/auth.ts, run the tests, open a PR`
- `merge it`

Everything lands on `chatgpt/*` → PR → required checks. `main` is reachable only through the PR.

## Limits to state honestly

- Not an agent fallback (web returns prose, not tool calls).
- The web session and your local agent cannot see each other; the repo is the only handoff.
- The daemon must be up; a sleeping machine removes the tools mid-conversation.
- One repo per writer.
- Required CI checks and human review are load-bearing — the model can be confidently wrong.
