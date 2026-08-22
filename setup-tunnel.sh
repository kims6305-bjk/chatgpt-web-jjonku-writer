#!/usr/bin/env bash
# Register the tunnel-client profile for this writer and run doctor.
set -euo pipefail
HOME_DIR="${WEBGPT_HOME:-$HOME/.local/share/webgpt-git-writer}"
PORT="${WEBGPT_PORT:-8791}"
export PATH="$HOME/.local/bin:$PATH"

[ -f "$HOME_DIR/tunnel.env" ] || { echo "missing tunnel.env — run ./set-key.sh first"; exit 1; }
[ -f "$HOME_DIR/writer.config.json" ] || { echo "missing writer.config.json — copy the example and edit it"; exit 1; }
set -a; . "$HOME_DIR/tunnel.env"; set +a

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile webgpt-writer \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --mcp-command "node $HOME_DIR/server.mjs" \
  --health-listen-addr "127.0.0.1:$PORT" \
  --force

tunnel-client doctor --profile webgpt-writer
echo
echo "If RESULT is ok, run ./install-service.sh"
