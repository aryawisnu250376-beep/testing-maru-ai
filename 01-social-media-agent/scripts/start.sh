#!/usr/bin/env bash
# Satu perintah (Linux/macOS/WSL2): bash scripts/start.sh
set -e
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
python -m pip install -r requirements.txt
python -m src.cli doctor
exec python -m src.dashboard --host 0.0.0.0 --port 8080
