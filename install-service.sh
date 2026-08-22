#!/usr/bin/env bash
# Keep the tunnel daemon running across reboots (launchd on macOS, systemd --user on Linux).
set -euo pipefail
HOME_DIR="${WEBGPT_HOME:-$HOME/.local/share/webgpt-git-writer}"

cat > "$HOME_DIR/start-tunnel.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH="\$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
set -a; . "$HOME_DIR/tunnel.env"; set +a
exec tunnel-client run --profile webgpt-writer
EOF
chmod +x "$HOME_DIR/start-tunnel.sh"

if [ "$(uname -s)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/ai.webgpt.gitwriter.tunnel.plist"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>ai.webgpt.gitwriter.tunnel</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$HOME_DIR/start-tunnel.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME_DIR/tunnel.log</string>
  <key>StandardErrorPath</key><string>$HOME_DIR/tunnel.log</string>
</dict>
</plist>
EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  sleep 6
  launchctl list | grep webgpt || true
else
  UNIT="$HOME/.config/systemd/user/webgpt-git-writer.service"
  mkdir -p "$(dirname "$UNIT")"
  cat > "$UNIT" <<EOF
[Unit]
Description=web ChatGPT git writer tunnel
[Service]
ExecStart=/bin/bash $HOME_DIR/start-tunnel.sh
Restart=always
StandardOutput=append:$HOME_DIR/tunnel.log
StandardError=append:$HOME_DIR/tunnel.log
[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now webgpt-git-writer.service
  systemctl --user --no-pager status webgpt-git-writer.service | head -5
fi

PORT="${WEBGPT_PORT:-8791}"
sleep 2
echo "readyz: $(curl -fsS "http://127.0.0.1:$PORT/readyz" || echo FAILED)"
echo
echo "Now connect ChatGPT: https://chatgpt.com/#settings/Connectors"
echo "  (+) custom connector -> Connection: Tunnel -> Authentication: No authentication"
