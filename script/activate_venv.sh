#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_ACTIVATE="$ROOT_DIR/venv/bin/activate"

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "venv が見つかりません: $VENV_ACTIVATE" >&2
  exit 1
fi

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "このスクリプトは source して使ってください。" >&2
  echo "例: source script/activate_venv.sh" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_ACTIVATE"
echo "venv を有効化しました: $VIRTUAL_ENV"
