#!/usr/bin/env bash
set -euo pipefail
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "Set TELEGRAM_BOT_TOKEN env var and rerun"
  exit 1
fi
python app/bot/run_polling.py
