#!/usr/bin/env bash
# Store the tunnel runtime key without echoing it or putting it in argv/history.
set -euo pipefail
HOME_DIR="${WEBGPT_HOME:-$HOME/.local/share/webgpt-git-writer}"
ENV_FILE="$HOME_DIR/tunnel.env"

read -rsp "Runtime API key (sk-...): " KEY; echo
[[ "$KEY" == sk-* ]] || { echo "not an sk- key"; exit 1; }
read -rp  "Tunnel id (tunnel_...): " TID
[[ "$TID" == tunnel_* ]] || { echo "not a tunnel_ id"; exit 1; }

umask 077
printf 'CONTROL_PLANE_API_KEY=%s\nCONTROL_PLANE_TUNNEL_ID=%s\n' "$KEY" "$TID" > "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "saved: $ENV_FILE (600)"
