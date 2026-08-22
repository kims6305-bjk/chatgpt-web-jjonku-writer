#!/usr/bin/env bash
# One-shot health report: daemon, doctor, guards, and whether ChatGPT actually called through.
set -uo pipefail
HOME_DIR="${WEBGPT_HOME:-$HOME/.local/share/webgpt-git-writer}"
PORT="${WEBGPT_PORT:-8791}"
export PATH="$HOME/.local/bin:$PATH"

echo "== daemon =="
curl -fsS "http://127.0.0.1:$PORT/readyz" && echo || echo "NOT READY"

echo "== doctor =="
if [ -f "$HOME_DIR/tunnel.env" ]; then
  set -a; . "$HOME_DIR/tunnel.env"; set +a
  tunnel-client doctor --profile webgpt-writer 2>&1 | tail -3
else
  echo "no tunnel.env"
fi

echo "== guards =="
( cd "$HOME_DIR" && node selfcheck.mjs )

echo "== calls forwarded from ChatGPT =="
if [ -f "$HOME_DIR/tunnel.log" ]; then
  grep -c 'forwarded command to MCP server' "$HOME_DIR/tunnel.log"
else
  echo "no tunnel.log yet"
fi
