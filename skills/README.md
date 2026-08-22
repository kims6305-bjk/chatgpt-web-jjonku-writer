# Skills

The same procedure in three packagings. `generic/PLAYBOOK.md` is the source; the others are it plus
a format-specific header.

| Path | Target | Install |
|---|---|---|
| `hermes/webgpt-tunnel-git-writer/SKILL.md` | Hermes · OpenClaw · Claude Code | copy the folder into your skills dir (e.g. `~/.hermes/skills/devops/`, `~/.claude/skills/`) |
| `codex/AGENTS.md` | Codex CLI | copy to your repo root, or merge into an existing `AGENTS.md` |
| `generic/PLAYBOOK.md` | any agent | paste, or point the agent at the raw URL |

`AGENTS.snippet.md` is different in kind: it is the paragraph you add to the **target repository's**
`AGENTS.md` so the web agent knows its own contract and prohibitions.

Keeping them in sync: edit `generic/PLAYBOOK.md`, then re-apply the two headers. The bodies are
byte-identical below their headers by design.
