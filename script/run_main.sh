#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/venv/bin/python"
MAIN_PY="$ROOT_DIR/main.py"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "venv の Python が見つかりません: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$MAIN_PY"
