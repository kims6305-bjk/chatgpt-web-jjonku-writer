#!/usr/bin/env bash
# Install the writer to a space-free path and fetch a checksum-verified tunnel-client.
set -euo pipefail

HOME_DIR="${WEBGPT_HOME:-$HOME/.local/share/webgpt-git-writer}"
BIN_DIR="$HOME/.local/bin"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$HOME_DIR" in *" "*)
  echo "ERROR: install path contains a space: $HOME_DIR"
  echo "tunnel-client splits its mcp.command on spaces and preflight will fail."
  exit 1;;
esac

mkdir -p "$HOME_DIR" "$BIN_DIR"
cp "$SRC/server.mjs" "$SRC/selfcheck.mjs" "$SRC/selfcheck-readonly.mjs" "$HOME_DIR/"
cp "$SRC/writer.config.example.json" "$SRC/writer.config.personal-pro.example.json" "$HOME_DIR/"
cp "$SRC/set-key.sh" "$SRC/setup-tunnel.sh" "$SRC/install-service.sh" "$SRC/verify.sh" "$HOME_DIR/"
chmod +x "$HOME_DIR"/*.sh
echo "writer -> $HOME_DIR"

if command -v tunnel-client >/dev/null 2>&1; then
  echo "tunnel-client already on PATH: $(command -v tunnel-client)"
else
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) A=darwin-arm64 ;;
    Darwin-x86_64) A=darwin-amd64 ;;
    Linux-x86_64) A=linux-amd64 ;;
    Linux-aarch64) A=linux-arm64 ;;
    *) echo "unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
  esac
  TAG="$(curl -sfL https://api.github.com/repos/openai/tunnel-client/releases/latest \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
  [ -n "$TAG" ] || { echo "could not resolve latest tunnel-client release"; exit 1; }
  ZIP="tunnel-client-${TAG}-${A}.zip"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  BASE="https://github.com/openai/tunnel-client/releases/download/${TAG}"
  echo "downloading ${ZIP} ..."
  curl -sfL -o "$TMP/$ZIP"  "$BASE/$ZIP"
  curl -sfL -o "$TMP/SUMS"  "$BASE/SHA256SUMS.txt"

  WANT="$(grep " $ZIP\$" "$TMP/SUMS" | awk '{print $1}')"
  if command -v sha256sum >/dev/null 2>&1; then GOT="$(sha256sum "$TMP/$ZIP" | awk '{print $1}')"
  else GOT="$(shasum -a 256 "$TMP/$ZIP" | awk '{print $1}')"; fi
  [ -n "$WANT" ] && [ "$WANT" = "$GOT" ] || { echo "CHECKSUM MISMATCH"; echo " want=$WANT"; echo "  got=$GOT"; exit 1; }
  echo "checksum ok"

  unzip -oq "$TMP/$ZIP" -d "$TMP/x"
  install -m 0755 "$TMP/x/tunnel-client" "$BIN_DIR/tunnel-client"
  xattr -d com.apple.quarantine "$BIN_DIR/tunnel-client" 2>/dev/null || true
  echo "tunnel-client -> $BIN_DIR/tunnel-client ($("$BIN_DIR/tunnel-client" --version))"
fi

cat <<EOF

Next:
  1) create a tunnel   https://platform.openai.com/settings/organization/tunnels
                       (fill ChatGPT workspaces — leaving it empty breaks discovery)
  2) create a key      https://platform.openai.com/settings/organization/api-keys
                       Restricted -> Tunnels: Read + Use
  3) cd "$HOME_DIR"
     cp writer.config.example.json writer.config.json   # edit repo_root / checks
     ./set-key.sh
     node selfcheck.mjs
     ./setup-tunnel.sh
     ./install-service.sh
EOF
