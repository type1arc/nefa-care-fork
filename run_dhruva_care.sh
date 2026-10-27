#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "[1/3] Creating Python virtual environment..."
  python3 -m venv .venv
fi
echo "[2/3] Installing/updating dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
echo "[3/3] Starting Dhruva Care..."
echo "Open http://127.0.0.1:5050/ in your browser."
.venv/bin/python app.py
