#!/usr/bin/env bash
# Pasang jadwal harian ke crontab (tanpa Hermes).
# Aman: hanya menyiapkan script + menunggu ACC. Render tidak jalan sendiri.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
PAGI="0 7 * * *"
SORE="0 16 * * *"
BLOK=$(cat <<CRON
# >>> ai-edukasi-agent (jangan diedit manual di antara penanda) >>>
$PAGI cd $ROOT && $PY -m src.cli script --json >/dev/null 2>&1 && $PY -m src.cli approve \$($PY -c "import sys;sys.path.insert(0,'.');from src import db;db.init();print(db.list_episodes(limit=1)[0]['id'])") >> $ROOT/data/cron.log 2>&1
$SORE cd $ROOT && $PY -m src.cli scan >> $ROOT/data/cron.log 2>&1
# <<< ai-edukasi-agent <<<
CRON
)
( crontab -l 2>/dev/null | sed '/>>> ai-edukasi-agent/,/<<< ai-edukasi-agent/d'; echo "$BLOK" ) | crontab -
echo "cron terpasang:"
crontab -l | sed -n '/>>> ai-edukasi-agent/,/<<< ai-edukasi-agent/p'
echo
echo "Log: $ROOT/data/cron.log"
