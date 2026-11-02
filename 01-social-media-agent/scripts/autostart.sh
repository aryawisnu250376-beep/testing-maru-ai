#!/usr/bin/env bash
# Pasang studio supaya hidup otomatis selama laptop menyala.
#   ./scripts/autostart.sh install    -> pasang di macOS (launchd) / Linux (systemd --user)
#   ./scripts/autostart.sh remove     -> lepas lagi
#   ./scripts/autostart.sh status     -> cek apakah sedang jalan
#
# Prinsipnya: satu proses, tidak butuh cron, tidak butuh VPS.
# Kalau laptop tidur, agent ikut tidur. Bangun, agent bangun.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$(command -v python3)"
CMD="$PY -m src.dashboard --port 8080 --no-worker"
NAME="ai-edukasi-studio"

case "${1:-status}" in
  install)
    if [[ "$(uname)" == "Darwin" ]]; then
      PLIST="$HOME/Library/LaunchAgents/$NAME.plist"
      mkdir -p "$(dirname "$PLIST")"
      cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$NAME</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>-m</string><string>src.dashboard</string>
    <string>--port</string><string>8080</string><string>--no-worker</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/data/studio.log</string>
  <key>StandardErrorPath</key><string>$ROOT/data/studio.log</string>
</dict></plist>
EOF
      launchctl unload "$PLIST" 2>/dev/null || true
      launchctl load "$PLIST"
      echo "terpasang (launchd): $PLIST"
    else
      UNIT="$HOME/.config/systemd/user/$NAME.service"
      mkdir -p "$(dirname "$UNIT")"
      cat > "$UNIT" <<EOF
[Unit]
Description=AI Edukasi Studio (agent otonom)
[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$CMD
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
EOF
      systemctl --user daemon-reload
      systemctl --user enable --now "$NAME"
      echo "terpasang (systemd --user): $UNIT"
      echo "catatan: agar tetap jalan setelah logout -> loginctl enable-linger $USER"
    fi
    ;;
  remove)
    if [[ "$(uname)" == "Darwin" ]]; then
      launchctl unload "$HOME/Library/LaunchAgents/$NAME.plist" 2>/dev/null || true
      rm -f "$HOME/Library/LaunchAgents/$NAME.plist"
    else
      systemctl --user disable --now "$NAME" 2>/dev/null || true
      rm -f "$HOME/.config/systemd/user/$NAME.service"
    fi
    echo "dilepas"
    ;;
  status)
    curl -s -o /dev/null -w "studio: HTTP %{http_code}\n" http://localhost:8080/ || echo "studio: tidak jalan"
    ;;
  *) echo "pakai: $0 {install|remove|status}"; exit 1 ;;
esac
