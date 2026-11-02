#!/usr/bin/env bash
# Jadwal harian tanpa Hermes (cron murni). Cocok kalau belum pasang agent.
#
# crontab -e lalu tambahkan:
#   0 7 * * *  /home/user/ai-edukasi-agent/scripts/daily.sh >> /home/user/ai-edukasi-agent/data/cron.log 2>&1
#
# Script ini HANYA menyiapkan script + menunggu ACC. Render tidak akan jalan
# sebelum kamu approve. Itu memang disengaja.

set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="/usr/local/bin:$PATH"
STAMP=$(date '+%Y-%m-%d %H:%M')

echo ""
echo "═══ $STAMP ═══"

# 1. Radar + script (LLM kalau tersedia, template kalau tidak)
OUT=$(python -m src.cli script --json 2>/dev/null | tail -1)
EP=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('episode_id',''))")

if [ -z "$EP" ]; then
  echo "✖ gagal membuat episode"
  exit 1
fi

# 2. Kirim untuk ACC (Telegram kalau diset, kalau tidak tulis decision.json)
python -m src.cli approve "$EP"

echo "→ episode $EP menunggu ACC kamu"
echo "   Telegram: balas ACC / TOLAK / EDIT: ..."
echo "   Atau:     python -m src.cli resume $EP"
